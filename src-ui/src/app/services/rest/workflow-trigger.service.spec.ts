import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { WorkflowTriggerService } from './workflow-trigger.service'
import {
  DocumentSource,
  WorkflowTrigger,
  WorkflowTriggerType,
} from 'src/app/data/workflow-trigger'

let httpTestingController: HttpTestingController
let service: WorkflowTriggerService
const endpoint = 'workflow_triggers'
const triggers: WorkflowTrigger[] = [
  {
    id: 1,
    type: WorkflowTriggerType.Consumption,
    filter_filename: '*test*',
    filter_path: null,
    sources: [DocumentSource.ApiUpload],
  },
  {
    id: 2,
    type: WorkflowTriggerType.DocumentAdded,
    filter_filename: null,
    filter_path: '/test/',
    sources: [DocumentSource.ConsumeFolder, DocumentSource.ApiUpload],
  },
]

// run common tests
commonAbstractPaperlessServiceTests(endpoint, WorkflowTriggerService)

describe(`Additional service tests for WorkflowTriggerService`, () => {
  it('should reload', () => {
    service.reload()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    req.flush({
      results: triggers,
    })
    expect(service.allWorkflows).toEqual(triggers)
  })

  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(WorkflowTriggerService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })
})
