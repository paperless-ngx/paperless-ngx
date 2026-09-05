import { NgbInputDatepickerConfig } from '@ng-bootstrap/ng-bootstrap'
import {
  getLocaleFirstDayOfWeek,
  localizedDatepickerConfigFactory,
} from './ngb-datepicker-config'

describe('localizedDatepickerConfigFactory', () => {
  it.each([
    ['en-US', 7],
    ['en-GB', 1],
  ])('sets the first day of the week for %s', (localeId, firstDay) => {
    const config = localizedDatepickerConfigFactory(localeId)

    expect(config).toBeInstanceOf(NgbInputDatepickerConfig)
    expect(config.firstDayOfWeek).toBe(firstDay)
  })
})

describe('getLocaleFirstDayOfWeek', () => {
  it('falls back to Monday when week info is unavailable', () => {
    const descriptor = Object.getOwnPropertyDescriptor(
      Intl.Locale.prototype,
      'getWeekInfo'
    )!
    Object.defineProperty(Intl.Locale.prototype, 'getWeekInfo', {
      ...descriptor,
      value: undefined,
    })

    try {
      expect(getLocaleFirstDayOfWeek('en-US')).toBe(1)
    } finally {
      Object.defineProperty(Intl.Locale.prototype, 'getWeekInfo', descriptor)
    }
  })
})
