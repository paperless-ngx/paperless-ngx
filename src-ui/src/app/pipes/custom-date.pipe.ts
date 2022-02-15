import { DatePipe } from '@angular/common';
import { Inject, LOCALE_ID, Pipe, PipeTransform } from '@angular/core';
import { SettingsService, SETTINGS_KEYS } from '../services/settings.service';

const FORMAT_TO_ISO_FORMAT = {
  "longDate": "y-MM-dd",
  "mediumDate": "y-MM-dd",
  "shortDate": "y-MM-dd"
}

@Pipe({
  name: 'customDate'
})
export class CustomDatePipe implements PipeTransform {

  private defaultLocale: string

  constructor(@Inject(LOCALE_ID) locale: string, private datePipe: DatePipe, private settings: SettingsService) {
    this.defaultLocale = locale
  }

  transform(value: any, format?: string, timezone?: string, locale?: string): string | null {
    let l = locale || this.settings.get(SETTINGS_KEYS.DATE_LOCALE) || this.defaultLocale
    let f = format || this.settings.get(SETTINGS_KEYS.DATE_FORMAT)
    if (l == "iso-8601") {
      return this.datePipe.transform(value, FORMAT_TO_ISO_FORMAT[f], timezone)
    } else {
      return this.datePipe.transform(value, format || this.settings.get(SETTINGS_KEYS.DATE_FORMAT), timezone, l)
    }
  }

}
