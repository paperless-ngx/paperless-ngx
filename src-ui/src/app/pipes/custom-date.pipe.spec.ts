import { TestBed } from '@angular/core/testing'
import { CustomDatePipe } from './custom-date.pipe'
import { SettingsService } from '../services/settings.service'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { DatePipe } from '@angular/common'

describe('CustomDatePipe', () => {
  let datePipe: CustomDatePipe

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [CustomDatePipe, SettingsService, DatePipe],
      imports: [HttpClientTestingModule],
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
})
