const nativeFetch = window.fetch.bind(window);
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const storageKey = (key) => `${key}:${document.body.dataset.user}`;

window.fetch = async (input, options = {}) => {
  const target = new URL(input instanceof Request ? input.url : input, window.location.href);
  if (target.origin !== window.location.origin) return nativeFetch(input, options);
  const headers = new Headers(input instanceof Request ? input.headers : undefined);
  new Headers(options.headers).forEach((value, name) => headers.set(name, value));
  headers.set('X-CSRF-Token', csrfToken);
  const response = await nativeFetch(input, {...options, headers});
  if (response.status === 401) {
    window.location.assign('/login');
    throw new Error('Sitzung abgelaufen. Bitte erneut anmelden.');
  }
  return response;
};
