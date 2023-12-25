import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { WorkflowActionService } from './workflow-action.service'
import { WorkflowAction } from 'src/app/data/workflow-action'

let httpTestingController: HttpTestingController
let service: WorkflowActionService
const endpoint = 'workflow_actions'
const actions: WorkflowAction[] = [
  {
    id: 1,
    assign_correspondent: 2,
  },
  {
    id: 2,
    assign_document_type: 1,
  },
]

// run common tests
commonAbstractPaperlessServiceTests(endpoint, WorkflowActionService)

describe(`Additional service tests for WorkflowActionService`, () => {
  it('should reload', () => {
    service.reload()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    req.flush({
      results: actions,
    })
    expect(service.allActions).toEqual(actions)
  })

  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(WorkflowActionService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })
})
