import { DatePipe } from '@angular/common';
import { Inject, LOCALE_ID, Pipe, PipeTransform } from '@angular/core';
import { SettingsService, SETTINGS_KEYS } from '../services/settings.service';

@Pipe({
  name: 'customDate'
})
export class CustomDatePipe extends DatePipe implements PipeTransform {

  constructor(@Inject(LOCALE_ID) locale: string, private settings: SettingsService) {
    super(settings.get(SETTINGS_KEYS.DATE_LOCALE) || locale)

  }

  transform(value: any, format?: string, timezone?: string, locale?: string): string | null {
    return super.transform(value, format || this.settings.get(SETTINGS_KEYS.DATE_FORMAT), timezone, locale)
  }

}
