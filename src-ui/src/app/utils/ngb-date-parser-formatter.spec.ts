import { TestBed } from '@angular/core/testing'
import { LocalizedDateParserFormatter } from './ngb-date-parser-formatter'
import { SettingsService } from '../services/settings.service'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

describe('LocalizedDateParserFormatter', () => {
  let dateParserFormatter: LocalizedDateParserFormatter
  let settingsService: SettingsService
  let httpTestingController: HttpTestingController

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        LocalizedDateParserFormatter,
        SettingsService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    dateParserFormatter = TestBed.inject(LocalizedDateParserFormatter)
    settingsService = TestBed.inject(SettingsService)
    httpTestingController = TestBed.inject(HttpTestingController)
  })

  it('should parse date to struct by locale', () => {
    let val = dateParserFormatter.parse('5/4/2023')
    expect(val).toEqual({ day: 4, month: 5, year: 2023 })
    val = dateParserFormatter.parse('5/4/23')
    expect(val.day).toEqual(4)
    expect(val.month).toEqual(5)
    expect(val.year).toEqual(2023)
    val = dateParserFormatter.parse('05042023')
    expect(val.day).toEqual(4)
    expect(val.month).toEqual(5)
    expect(val.year).toEqual(2023)
    val = dateParserFormatter.parse('12/13')
    expect(val.day).toEqual(13)
    expect(val.month).toEqual(12)
    expect(val.year).toEqual(new Date().getFullYear())

    settingsService.setLanguage('de-de') // dd.mm.yyyy
    val = dateParserFormatter.parse('04.05.2023')
    expect(val).toEqual({ day: 4, month: 5, year: 2023 })
    val = dateParserFormatter.parse('04052023')
    expect(val).toEqual({ day: 4, month: 5, year: 2023 })

    settingsService.setLanguage('tr-tr') // yyyy-mm-dd
    val = dateParserFormatter.parse('2023-05-04')
    expect(val).toEqual({ day: 4, month: 5, year: 2023 })
    val = dateParserFormatter.parse('20230504')
    expect(val).toEqual({ day: 4, month: 5, year: 2023 })
  })

  it('should parse date struct to string by locale', () => {
    const dateStruct = {
      day: 4,
      month: 5,
      year: 2023,
    }
    let dateStr = dateParserFormatter.format(dateStruct)
    expect(dateStr).toEqual('05/04/2023')

    settingsService.setLanguage('de-de') // dd.mm.yyyy
    dateStr = dateParserFormatter.format(dateStruct)
    expect(dateStr).toEqual('04.05.2023')
  })
})
