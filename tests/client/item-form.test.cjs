const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { test } = require('node:test');
const { runInNewContext } = require('node:vm');

const source = readFileSync(resolve(__dirname, '../../app/static/item-form.js'), 'utf8');

// Exercise the shipped event handlers with a small DOM contract, without npm dependencies.
class Element extends EventTarget {
  constructor() {
    super();
    this.hidden = false;
    this.disabled = false;
    this.value = '';
    this.textContent = '';
    this.innerHTML = 'Post item';
    this.attributes = new Map();
    this.classList = { toggle() {}, add() {}, remove() {} };
  }
  setAttribute(name, value) { this.attributes.set(name, value); }
  removeAttribute(name) { delete this[name]; }
  focus() { this.focused = true; }
  click() {
    assert.equal(this.hidden, false, 'Recovery must be reachable through a visible control');
    this.dispatchEvent(new Event('click'));
  }
}

function mount({ currentUrl = '' } = {}) {
  const input = new Element();
  input.files = [];
  Object.defineProperty(input, 'value', {
    get() { return this.files.length ? 'C:\\fakepath\\' + this.files[0].name : ''; },
    set(value) { if (value === '') this.files = []; },
  });
  const link = new Element();
  const remove = currentUrl ? new Element() : null;
  if (remove) remove.checked = false;
  const preview = new Element();
  const reset = new Element();
  reset.hidden = true;
  const message = new Element();
  const button = new Element();
  const picker = new Element();
  const controls = new Map([
    ['[name=image_file]', input], ['[name=image_url]', link],
    ['[name=remove_image]', remove], ['[data-photo-dropzone]', new Element()],
    ['[data-photo-preview]', preview], ['[data-photo-empty]', new Element()],
    ['[data-photo-message]', message], ['[data-photo-reset]', reset],
    ['[data-photo-drag-hint]', new Element()],
  ]);
  picker.dataset = { currentUrl };
  picker.querySelector = (selector) => {
    assert.ok(controls.has(selector), 'Unexpected picker query: ' + selector);
    return controls.get(selector);
  };
  const fields = {
    title: 'Text entered before choosing a photo',
    description: 'Keep this description when a photo is rejected.',
    price: '12', category: 'Furniture', condition: 'Good', csrf_token: 'test-only',
  };
  const form = new Element();
  form.action = '/items/new';
  form.querySelector = (selector) => {
    if (selector === '[data-photo-picker]') return picker;
    if (selector === 'button[type=submit]') return button;
    throw new Error('Unexpected form query: ' + selector);
  };
  const posts = [];
  const destinations = [];
  const fetch = async (url, options) => {
    posts.push({ url, ...options });
    return {
      ok: true, redirected: false,
      headers: { get: () => 'application/json' },
      json: async () => ({ redirect_url: '/items/posted' }),
    };
  };
  runInNewContext(source, {
    document: {
      querySelectorAll: (selector) => {
        assert.equal(selector, '.item-form');
        return [form];
      },
    },
    window: {
      fetch, addEventListener() {},
      location: { assign: (url) => destinations.push(url) },
    },
    URL: { createObjectURL: () => 'blob:test-photo', revokeObjectURL() {} },
    FormData: class {
      constructor() {
        this.fields = { ...fields, image_url: link.value };
        this.photo = input.files[0];
      }
    },
    fetch,
  }, { filename: 'app/static/item-form.js' });
  return {
    input, link, remove, preview, reset, message, button, fields, posts, destinations,
    select(file) {
      input.files = [file];
      input.dispatchEvent(new Event('change'));
    },
    async submit() {
      const event = new Event('submit', { cancelable: true });
      form.dispatchEvent(event);
      assert.equal(event.defaultPrevented, true);
      // Flush the real async submit handler and mocked network promises.
      await new Promise(setImmediate);
    },
  };
}

const rejectedFiles = [
  ['oversized photo', { name: 'large.jpg', size: 5 * 1024 * 1024 + 1 }],
  ['unsupported file', { name: 'photo.gif', size: 100 }],
  ['empty file', { name: 'empty.png', size: 0 }],
];
for (const [context, currentUrl] of [['new listing', ''], ['existing photo', '/uploads/current.jpg']]) {
  for (const [reason, file] of rejectedFiles) {
    test(`${context}: discard ${reason} and submit without a new photo`, async () => {
      const page = mount({ currentUrl });
      const entered = { ...page.fields };
      page.select(file);
      assert.equal(page.input.files.length, 0);
      assert.equal(page.input.attributes.get('aria-invalid'), 'true');
      assert.equal(page.reset.hidden, false, 'Rejected optional photo must remain clearable');
      await page.submit();
      assert.equal(page.posts.length, 0, 'Do not submit until the photo error is resolved');

      page.reset.click();
      assert.equal(page.message.textContent, '');
      assert.equal(page.input.attributes.get('aria-invalid'), 'false');
      assert.equal(page.input.files.length, 0);
      assert.deepEqual(page.fields, entered);
      assert.equal(page.preview.hidden, !currentUrl);
      if (currentUrl) assert.equal(page.preview.src, currentUrl);
      if (page.remove) assert.equal(page.remove.checked, false);
      assert.equal(page.reset.hidden, true);

      await page.submit();
      assert.equal(page.posts.length, 1);
      assert.equal(page.posts[0].method, 'POST');
      assert.equal(page.posts[0].body.photo, undefined);
      assert.deepEqual(page.posts[0].body.fields, { ...entered, image_url: '' });
      assert.deepEqual(page.destinations, ['/items/posted']);
      assert.equal(page.button.disabled, false);
    });
  }
}

test('a valid photo still submits normally', async () => {
  const page = mount();
  const file = { name: 'lamp.png', size: 1024 };
  page.select(file);
  await page.submit();
  assert.equal(page.posts.length, 1);
  assert.equal(page.posts[0].body.photo, file);
});

test('a valid selection also recovers after a rejected photo', async () => {
  const page = mount();
  page.select(rejectedFiles[0][1]);
  const file = { name: 'replacement.jpg', size: 1024 };
  page.select(file);
  await page.submit();
  assert.equal(page.posts.length, 1);
  assert.equal(page.posts[0].body.photo, file);
});

test('a photo exactly at the 5 MB limit is accepted', async () => {
  const page = mount();
  const file = { name: 'at-limit.jpg', size: 5 * 1024 * 1024 };
  page.select(file);
  assert.equal(page.input.files.length, 1);
  await page.submit();
  assert.equal(page.posts.length, 1);
  assert.equal(page.posts[0].body.photo, file);
});
