import { TestBed } from '@angular/core/testing'

import { ConfigService } from './config.service'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'
import { OutputTypeConfig, EdocConfig } from '../data/./edoc-config'

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
      } as EdocConfig)
      .subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}config/1/`
    )
    expect(req.request.method).toEqual('PATCH')
  })

  it('should support upload file with form data', () => {
    service.uploadFile(new File([], 'test.png'), 1, 'app_logo').subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}config/1/`
    )
    expect(req.request.method).toEqual('PATCH')
    expect(req.request.body).not.toBeNull()
  })

  it('should not pass string app_logo', () => {
    service
      .saveConfig({
        id: 1,
        app_logo: '/logo/foobar.png',
      } as EdocConfig)
      .subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}config/1/`
    )
    expect(req.request.body).toEqual({ id: 1 })
  })
})
