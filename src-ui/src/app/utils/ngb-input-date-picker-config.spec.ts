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
})
