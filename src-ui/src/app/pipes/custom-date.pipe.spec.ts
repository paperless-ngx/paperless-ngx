import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { SettingsService } from '../services/settings.service'
import { CustomDatePipe } from './custom-date.pipe'

describe('CustomDatePipe', () => {
  let datePipe: CustomDatePipe

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        CustomDatePipe,
        SettingsService,
        DatePipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    datePipe = TestBed.inject(CustomDatePipe)
  })

  it('should parse date strings with additional options', () => {
    expect(datePipe.transform('5/4/23')).toEqual('May 4, 2023')
    expect(
      datePipe.transform(
        '5/4/23',
        'mediumDate',
        'America/Los_Angeles',
        'iso-8601'
      )
    ).toEqual('2023-05-04')
  })

  it('should support relative date formatting', () => {
    const now = new Date()
    const notNow = new Date(now)
    notNow.setDate(now.getDate() - 1)
    expect(datePipe.transform(notNow, 'relative')).toEqual('1 day ago')
    notNow.setDate(now.getDate())
    notNow.setMonth(now.getMonth() - 1)
    expect(datePipe.transform(notNow, 'relative')).toEqual('1 month ago')
    expect(datePipe.transform(now, 'relative')).toEqual('Just now')
  })
})
