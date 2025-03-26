import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { commonAbstractEdocServiceTests } from './abstract-edoc-service.spec'
import { WorkflowService } from './workflow.service'
import { Workflow } from 'src/app/data/workflow'
import {
  DocumentSource,
  WorkflowTriggerType,
} from 'src/app/data/workflow-trigger'
import { WorkflowActionType } from 'src/app/data/workflow-action'

let httpTestingController: HttpTestingController
let service: WorkflowService
const endpoint = 'workflows'
const workflows: Workflow[] = [
  {
    name: 'Workflow 1',
    id: 1,
    order: 1,
    enabled: true,
    triggers: [
      {
        id: 1,
        type: WorkflowTriggerType.Consumption,
        sources: [DocumentSource.ConsumeFolder],
        filter_filename: '*',
      },
    ],
    actions: [
      {
        id: 1,
        type: WorkflowActionType.Assignment,
        assign_title: 'foo',
      },
    ],
  },
  {
    name: 'Workflow 2',
    id: 2,
    order: 2,
    enabled: true,
    triggers: [
      {
        id: 2,
        type: WorkflowTriggerType.DocumentAdded,
        filter_filename: 'foo',
      },
    ],
    actions: [
      {
        id: 2,
        type: WorkflowActionType.Assignment,
        assign_title: 'bar',
      },
    ],
  },
]

// run common tests
commonAbstractEdocServiceTests(endpoint, WorkflowService)

describe(`Additional service tests for WorkflowService`, () => {
  it('should reload', () => {
    service.reload()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    req.flush({
      results: workflows,
    })
    expect(service.allWorkflows).toEqual(workflows)
  })

  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(WorkflowService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })
})
