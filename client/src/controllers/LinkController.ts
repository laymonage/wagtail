import { Controller } from '@hotwired/stimulus';

export class LinkController extends Controller<HTMLElement> {
  static values = {
    attrName: { default: 'href', type: String },
    preserveKeys: { default: [], type: Array },
  };

  declare attrNameValue: string;
  declare preserveKeysValue: string[];

  get url() {
    return new URL(
      this.element.getAttribute(this.attrNameValue) || '',
      window.location.href,
    );
  }

  connect() {
    this.setParamsFromLocation();
  }

  setParamsFromURL(url: URL) {
    // New params to build the new URL
    const params = new URLSearchParams(url.search);

    // Don't take the ones we want to preserve from the current URL
    params.forEach((_, key) => {
      if (this.preserveKeysValue.includes(key)) {
        params.delete(key);
      }
    });

    // Add the ones we want to preserve from the current URL to the new params
    const currentUrl = this.url;
    currentUrl.searchParams.forEach((value, key) => {
      if (this.preserveKeysValue.includes(key)) {
        params.append(key, value);
      }
    });

    currentUrl.search = params.toString();
    this.element.setAttribute(this.attrNameValue, currentUrl.toString());
  }

  setParamsFromSwapRequest(e: CustomEvent<{ requestUrl?: string }>) {
    if (!e.detail?.requestUrl) return;
    this.setParamsFromURL(new URL(e.detail.requestUrl, window.location.href));
  }

  setParamsFromLocation() {
    this.setParamsFromURL(new URL(window.location.href));
  }
}
