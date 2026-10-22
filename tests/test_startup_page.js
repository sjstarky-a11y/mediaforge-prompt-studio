// Exercise the startup UI without loading models or waiting a real minute.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

async function page(responses, start = 0) {
  const elements = {
    status: {textContent: "Starting MediaForge"},
    retry: {hidden: true, addEventListener: (_event, action) => { elements.retry.click = action; }},
    spinner: {hidden: false},
  };
  let now = start;
  let reloads = 0;
  const timers = new Map();
  let next = 0;
  const script = fs.readFileSync(path.join(__dirname, "../app/startup.html"), "utf8")
    .match(/<script>([\s\S]*?)<\/script>/)[1];
  const context = {
    document: {getElementById: name => elements[name]},
    window: {location: {reload: () => reloads++}},
    Date: {now: () => now},
    AbortController,
    setTimeout: (action, delay) => { const id = ++next; timers.set(id, {action, delay}); return id; },
    clearTimeout: id => timers.delete(id),
    fetch: async (url, options) => {
      assert.equal(url, "/health");
      assert.equal(options.cache, "no-store");
      assert.ok(options.signal);
      const response = responses.shift();
      if (response instanceof Error) throw response;
      assert.notEqual(response, undefined, "Unexpected request");
      return response;
    },
  };
  await vm.runInNewContext(script, context);
  return {
    elements, timers, reloads: () => reloads,
    advance: milliseconds => { now += milliseconds; },
    poll: async () => {
      const entry = [...timers].find(([, timer]) => timer.delay === 500);
      assert.ok(entry, "Readiness poll must be scheduled");
      timers.delete(entry[0]);
      await entry[1].action();
    },
  };
}

(async () => {
  const ready = await page([{ok: false}, {ok: true}]);
  assert.equal(ready.reloads(), 0, "Never open an unready app");
  await ready.poll();
  assert.equal(ready.reloads(), 1, "Open automatically once ready");
  assert.equal(ready.timers.size, 0);

  const failed = await page([new Error("temporary disconnect"), {ok: false}, {ok: true}]);
  failed.advance(60000);
  await failed.poll();
  assert.equal(failed.reloads(), 0);
  assert.equal(failed.elements.retry.hidden, false);
  assert.equal(failed.elements.spinner.hidden, true);
  assert.match(failed.elements.status.textContent, /Logs tab/);
  assert.equal(failed.timers.size, 0, "Stop polling on timeout");
  failed.elements.retry.click();
  await new Promise(setImmediate);
  assert.equal(failed.elements.retry.hidden, true);
  assert.equal(failed.reloads(), 1, "Retry can recover without manual refresh");
  console.log("Startup page: readiness, network recovery, timeout and retry passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
