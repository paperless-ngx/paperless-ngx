import { LOCALE_ID } from '@angular/core'
import { TestBed } from '@angular/core/testing'
import { NgbInputDatepickerConfig } from '@ng-bootstrap/ng-bootstrap'
import { PngxDatePickerConfig } from './ngb-input-date-picker-config'

describe('PngxDatePickerConfig', () => {
  const configureLocale = (locale: string) => {
    TestBed.configureTestingModule({
      providers: [
        { provide: LOCALE_ID, useValue: locale },
        {
          provide: NgbInputDatepickerConfig,
          useClass: PngxDatePickerConfig,
        },
      ],
    })
  }

  it('uses Sunday as the first day of the week for en-US', () => {
    configureLocale('en-US')

    const config = TestBed.inject(NgbInputDatepickerConfig)

    expect(config).toBeInstanceOf(PngxDatePickerConfig)
    expect(config.firstDayOfWeek).toEqual(7)
  })

  it('uses Monday as the first day of the week for de-DE', () => {
    configureLocale('de-DE')

    const config = TestBed.inject(NgbInputDatepickerConfig)

    expect(config.firstDayOfWeek).toEqual(1)
  })

  it('supports browsers that provide getWeekInfo() and weekInfo', () => {
    const getWeekInfo = jest.fn().mockReturnValue({ firstDay: 6 })
    const originalDescriptor = Object.getOwnPropertyDescriptor(
      Intl.Locale.prototype,
      'getWeekInfo'
    )
    Object.defineProperty(Intl.Locale.prototype, 'getWeekInfo', {
      configurable: true,
      value: getWeekInfo,
    })
    let config: NgbInputDatepickerConfig
    try {
      configureLocale('ar-EG')
      config = TestBed.inject(NgbInputDatepickerConfig)
    } finally {
      if (originalDescriptor) {
        Object.defineProperty(
          Intl.Locale.prototype,
          'getWeekInfo',
          originalDescriptor
        )
      } else {
        delete Intl.Locale.prototype['getWeekInfo']
      }
    }

    expect(getWeekInfo).toHaveBeenCalledTimes(1)
    expect(config.firstDayOfWeek).toEqual(6)

    Object.defineProperty(Intl.Locale.prototype, 'weekInfo', {
      configurable: true,
      value: { firstDay: 5 },
    })
    Object.defineProperty(Intl.Locale.prototype, 'getWeekInfo', {
      configurable: true,
      value: undefined,
    })
    try {
      TestBed.resetTestingModule()
      configureLocale('ar-EG')
      config = TestBed.inject(NgbInputDatepickerConfig)
    } finally {
      delete Intl.Locale.prototype['weekInfo']
      delete Intl.Locale.prototype['getWeekInfo']
    }

    expect(config.firstDayOfWeek).toEqual(5)
  })
})
