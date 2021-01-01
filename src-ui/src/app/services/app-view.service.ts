import { Inject, Injectable, Renderer2, RendererFactory2 } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { SettingsService, SETTINGS_KEYS } from './settings.service';

@Injectable({
  providedIn: 'root'
})
export class AppViewService {
  private renderer: Renderer2;

  constructor(
    private settings: SettingsService,
    private rendererFactory: RendererFactory2,
    @Inject(DOCUMENT) private document
  ) {
    this.renderer = rendererFactory.createRenderer(null, null);

    this.updateDarkModeSettings()
  }

  updateDarkModeSettings(): void {
    let darkModeUseSystem = this.settings.get(SETTINGS_KEYS.DARK_MODE_USE_SYSTEM)
    let darkModeEnabled = this.settings.get(SETTINGS_KEYS.DARK_MODE_ENABLED)

    if (darkModeUseSystem) {
      this.renderer.addClass(this.document.body, 'color-scheme-system')
      this.renderer.removeClass(this.document.body, 'color-scheme-dark')
    } else {
      this.renderer.removeClass(this.document.body, 'color-scheme-system')
      darkModeEnabled ? this.renderer.addClass(this.document.body, 'color-scheme-dark') : this.renderer.removeClass(this.document.body, 'color-scheme-dark')
    }

  }

}
