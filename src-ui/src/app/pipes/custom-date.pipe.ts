import { DatePipe } from '@angular/common'
import { Inject, LOCALE_ID, Pipe, PipeTransform } from '@angular/core'
import { SETTINGS_KEYS } from '../data/ui-settings'
import { SettingsService } from '../services/settings.service'

const FORMAT_TO_ISO_FORMAT = {
  longDate: 'y-MM-dd',
  mediumDate: 'y-MM-dd',
  shortDate: 'y-MM-dd',
}

@Pipe({
  name: 'customDate',
})
export class CustomDatePipe implements PipeTransform {
  private defaultLocale: string

  constructor(
    @Inject(LOCALE_ID) locale: string,
    private datePipe: DatePipe,
    private settings: SettingsService
  ) {
    this.defaultLocale = locale
  }

  transform(
    value: any,
    format?: string,
    timezone?: string,
    locale?: string
  ): string | null {
    let l =
      locale ||
      this.settings.get(SETTINGS_KEYS.DATE_LOCALE) ||
      this.defaultLocale
    let f = format || this.settings.get(SETTINGS_KEYS.DATE_FORMAT)
    if (format === 'relative') {
      const seconds = Math.floor((+new Date() - +new Date(value)) / 1000)
      if (seconds < 60) return $localize`Just now`
      const intervals = {
        year: {
          label: $localize`year ago`,
          labelPlural: $localize`years ago`,
          interval: 31536000,
        },
        month: {
          label: $localize`month ago`,
          labelPlural: $localize`months ago`,
          interval: 2592000,
        },
        week: {
          label: $localize`week ago`,
          labelPlural: $localize`weeks ago`,
          interval: 604800,
        },
        day: {
          label: $localize`day ago`,
          labelPlural: $localize`days ago`,
          interval: 86400,
        },
        hour: {
          label: $localize`hour ago`,
          labelPlural: $localize`hours ago`,
          interval: 3600,
        },
        minute: {
          label: $localize`minute ago`,
          labelPlural: $localize`minutes ago`,
          interval: 60,
        },
      }
      let counter
      for (const i in intervals) {
        counter = Math.floor(seconds / intervals[i].interval)
        if (counter > 0) {
          const label =
            counter > 1 ? intervals[i].labelPlural : intervals[i].label
          return `${counter} ${label}`
        }
      }
    }
    if (l == 'iso-8601') {
      return this.datePipe.transform(value, FORMAT_TO_ISO_FORMAT[f], timezone)
    } else {
      return this.datePipe.transform(
        value,
        format || this.settings.get(SETTINGS_KEYS.DATE_FORMAT),
        timezone,
        l
      )
    }
  }
}
