import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { ConsumptionTemplateService } from './consumption-template.service'
import {
  DocumentSource,
  PaperlessConsumptionTemplate,
} from 'src/app/data/paperless-consumption-template'

let httpTestingController: HttpTestingController
let service: ConsumptionTemplateService
const endpoint = 'consumption_templates'
const templates: PaperlessConsumptionTemplate[] = [
  {
    name: 'Template 1',
    id: 1,
    order: 1,
    filter_filename: '*test*',
    filter_path: null,
    sources: [DocumentSource.ApiUpload],
    assign_correspondent: 2,
  },
  {
    name: 'Template 2',
    id: 2,
    order: 2,
    filter_filename: null,
    filter_path: '/test/',
    sources: [DocumentSource.ConsumeFolder, DocumentSource.ApiUpload],
    assign_document_type: 1,
  },
]

// run common tests
commonAbstractPaperlessServiceTests(
  'consumption_templates',
  ConsumptionTemplateService
)

describe(`Additional service tests for ConsumptionTemplateService`, () => {
  it('should reload', () => {
    service.reload()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    req.flush({
      results: templates,
    })
    expect(service.allTemplates).toEqual(templates)
  })

  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(ConsumptionTemplateService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })
})
