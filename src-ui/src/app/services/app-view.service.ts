import { Inject, Injectable, Renderer2, RendererFactory2 } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { GENERAL_SETTINGS } from 'src/app/data/storage-keys';

@Injectable({
  providedIn: 'root'
})
export class AppViewService {
  private renderer: Renderer2;

  constructor(rendererFactory: RendererFactory2, @Inject(DOCUMENT) private document) {
    this.renderer = rendererFactory.createRenderer(null, null);

    this.updateDarkModeSettings()
  }

  updateDarkModeSettings() {
    let darkModeUseSystem = JSON.parse(localStorage.getItem(GENERAL_SETTINGS.DARK_MODE_USE_SYSTEM)) && GENERAL_SETTINGS.DARK_MODE_USE_SYSTEM_DEFAULT
    let darkModeEnabled = JSON.parse(localStorage.getItem(GENERAL_SETTINGS.DARK_MODE_ENABLED)) || GENERAL_SETTINGS.DARK_MODE_ENABLED_DEFAULT

    if (darkModeUseSystem) {
      this.renderer.addClass(this.document.body, 'dark-mode-preferred')
      this.renderer.removeClass(this.document.body, 'dark-mode')
    } else {
      this.renderer.removeClass(this.document.body, 'dark-mode-preferred')
      darkModeEnabled ? this.renderer.addClass(this.document.body, 'dark-mode') : this.renderer.removeClass(this.document.body, 'dark-mode')
    }

  }

}
