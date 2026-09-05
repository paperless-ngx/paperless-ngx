import { NgbInputDatepickerConfig } from '@ng-bootstrap/ng-bootstrap'

interface LocaleWithWeekInfo extends Intl.Locale {
  getWeekInfo?: () => { firstDay: number }
}

const ISO_FIRST_DAY_OF_WEEK = 1

export function getLocaleFirstDayOfWeek(localeId: string): number {
  try {
    const locale = new Intl.Locale(localeId) as LocaleWithWeekInfo
    const firstDay = locale.getWeekInfo?.().firstDay

    return firstDay >= 1 && firstDay <= 7 ? firstDay : ISO_FIRST_DAY_OF_WEEK
  } catch {
    return ISO_FIRST_DAY_OF_WEEK
  }
}

export function localizedDatepickerConfigFactory(
  localeId: string
): NgbInputDatepickerConfig {
  const config = new NgbInputDatepickerConfig()
  config.firstDayOfWeek = getLocaleFirstDayOfWeek(localeId)
  return config
}
