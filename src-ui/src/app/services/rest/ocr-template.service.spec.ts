import { provideHttpClient } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { OcrZoneTransform, ZoneTestRequest } from 'src/app/data/ocr-template'
import { environment } from 'src/environments/environment'
import { OcrTemplateService } from './ocr-template.service'

describe('OcrTemplateService', () => {
  let service: OcrTemplateService
  let http: HttpTestingController

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    })
    service = TestBed.inject(OcrTemplateService)
    http = TestBed.inject(HttpTestingController)
  })

  afterEach(() => http.verify())

  it('builds page image URLs with zero-based page numbers', () => {
    expect(service.getPageImageUrl(12, 0)).toBe(
      `${environment.apiBaseUrl}ocr_templates/document-page-image/12/0/`
    )
    expect(service.getPageImageUrl(12, 2)).toBe(
      `${environment.apiBaseUrl}ocr_templates/document-page-image/12/2/`
    )
  })

  it('posts a zone test and returns the extraction result', () => {
    const zone: ZoneTestRequest = {
      name: 'Total',
      x: 10,
      y: 20,
      width: 100,
      height: 50,
      page: -1,
      ocr_language: 'eng',
      transform: OcrZoneTransform.Numeric,
      validation_regex: '\\d+',
      zone_source_width: 1000,
      zone_source_height: 1500,
    }
    const result = {
      raw_text: 'Total: 123',
      value: '123',
      regex: '\\d+',
      regex_match: true,
    }
    const next = jest.fn()
    service.testZone(12, zone).subscribe(next)
    const request = http.expectOne(
      `${environment.apiBaseUrl}ocr_templates/test-zone/`
    )
    expect(request.request.method).toBe('POST')
    expect(request.request.body).toEqual({ document: 12, zone })
    request.flush(result)
    expect(next).toHaveBeenCalledWith(result)
  })

  it('passes zone-test failures to the caller', () => {
    const error = jest.fn()
    service.testZone(12, {} as ZoneTestRequest).subscribe({ error })
    http
      .expectOne(`${environment.apiBaseUrl}ocr_templates/test-zone/`)
      .flush(
        { error: 'Invalid zone' },
        { status: 400, statusText: 'Bad Request' }
      )
    expect(error).toHaveBeenCalledWith(
      expect.objectContaining({ status: 400, error: { error: 'Invalid zone' } })
    )
  })
})
