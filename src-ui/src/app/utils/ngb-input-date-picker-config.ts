import { inject, Injectable, LOCALE_ID } from '@angular/core'
import { NgbInputDatepickerConfig } from '@ng-bootstrap/ng-bootstrap'

@Injectable()
export class PngxDatePickerConfig extends NgbInputDatepickerConfig {
  currentLocale = inject(LOCALE_ID)

  constructor() {
    super()
    const localeInfo = new Intl.Locale(this.currentLocale)
    // getWeekInfo returns an object containing 'firstDay' (1 = Monday, 7 = Sunday)
    if ('getWeekInfo' in localeInfo) {
      const firstDay = (localeInfo as any).getWeekInfo().firstDay
      this.firstDayOfWeek = firstDay
    }
  }
}
