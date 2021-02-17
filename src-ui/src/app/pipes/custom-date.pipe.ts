import { DatePipe } from '@angular/common';
import { Inject, LOCALE_ID, Pipe, PipeTransform } from '@angular/core';
import { SettingsService, SETTINGS_KEYS } from '../services/settings.service';

const FORMAT_TO_ISO_FORMAT = {
  "longDate": "y-MM-dd",
  "mediumDate": "yy-MM-dd",
  "shortDate": "yy-MM-dd"
}

@Pipe({
  name: 'customDate'
})
export class CustomDatePipe extends DatePipe implements PipeTransform {

  constructor(@Inject(LOCALE_ID) locale: string, private settings: SettingsService) {
    super(locale)
  }

  transform(value: any, format?: string, timezone?: string, locale?: string): string | null {
    let l = locale || this.settings.get(SETTINGS_KEYS.DATE_LOCALE)
    let f = format || this.settings.get(SETTINGS_KEYS.DATE_FORMAT)
    if (l == "iso-8601") {
      return super.transform(value, FORMAT_TO_ISO_FORMAT[f], timezone)
    } else {
      return super.transform(value, format || this.settings.get(SETTINGS_KEYS.DATE_FORMAT), timezone, locale)
    }
  }

}
