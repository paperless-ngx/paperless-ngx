import { inject, Injectable, LOCALE_ID } from '@angular/core'
import { NgbInputDatepickerConfig } from '@ng-bootstrap/ng-bootstrap'

@Injectable()
export class PngxDatePickerConfig extends NgbInputDatepickerConfig {
  currentLocale = inject(LOCALE_ID)

  constructor() {
    super()
    const localeInfo = new Intl.Locale(this.currentLocale) as any
    let firstDay
    if (localeInfo?.getWeekInfo) firstDay = localeInfo.getWeekInfo?.().firstDay
    else if (localeInfo?.weekInfo?.firstDay)
      firstDay = localeInfo.weekInfo.firstDay

    if (firstDay !== undefined) {
      this.firstDayOfWeek = firstDay
    }
  }
}
