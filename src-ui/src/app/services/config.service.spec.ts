import { TestBed } from '@angular/core/testing'

import { ConfigService } from './config.service'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'
import { OutputTypeConfig, PaperlessConfig } from '../data/paperless-config'

describe('ConfigService', () => {
  let service: ConfigService
  let httpTestingController: HttpTestingController

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
    })
    service = TestBed.inject(ConfigService)
    httpTestingController = TestBed.inject(HttpTestingController)
  })

  it('should call correct API endpoint on get config', () => {
    service.getConfig().subscribe()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}config/`)
      .flush([{}])
  })

  it('should call correct API endpoint on set config', () => {
    service
      .saveConfig({
        id: 1,
        output_type: OutputTypeConfig.PDF_A,
      } as PaperlessConfig)
      .subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}config/1/`
    )
    expect(req.request.method).toEqual('PATCH')
  })
})
