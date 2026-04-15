import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { PaperlessTaskStatus, PaperlessTaskType } from '../data/paperless-task'
import { TasksService } from './tasks.service'

describe('TasksService', () => {
  let httpTestingController: HttpTestingController
  let tasksService: TasksService

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        TasksService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    tasksService = TestBed.inject(TasksService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  it('calls tasks api endpoint on reload', () => {
    tasksService.reload()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}tasks/?task_type=consume_file&acknowledged=false`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('does not call tasks api endpoint on reload if already loading', () => {
    tasksService.loading = true
    tasksService.reload()
    httpTestingController.expectNone(
      `${environment.apiBaseUrl}tasks/?task_type=consume_file&acknowledged=false`
    )
  })

  it('calls acknowledge_tasks api endpoint on dismiss and reloads', () => {
    tasksService.dismissTasks(new Set([1, 2, 3])).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}tasks/acknowledge/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({
      tasks: [1, 2, 3],
    })
    req.flush([])
    // reload is then called
    httpTestingController
      .expectOne(
        `${environment.apiBaseUrl}tasks/?task_type=consume_file&acknowledged=false`
      )
      .flush([])
  })

  it('sorts tasks returned from api', () => {
    expect(tasksService.total).toEqual(0)
    const mockTasks = [
      {
        task_type: PaperlessTaskType.ConsumeFile,
        status: PaperlessTaskStatus.Success,
        acknowledged: false,
        task_id: '1234',
        input_data: { filename: 'file1.pdf' },
        date_created: new Date(),
        related_document_ids: [],
      },
      {
        task_type: PaperlessTaskType.ConsumeFile,
        status: PaperlessTaskStatus.Failure,
        acknowledged: false,
        task_id: '1235',
        input_data: { filename: 'file2.pdf' },
        date_created: new Date(),
        related_document_ids: [],
      },
      {
        task_type: PaperlessTaskType.ConsumeFile,
        status: PaperlessTaskStatus.Pending,
        acknowledged: false,
        task_id: '1236',
        input_data: { filename: 'file3.pdf' },
        date_created: new Date(),
        related_document_ids: [],
      },
      {
        task_type: PaperlessTaskType.ConsumeFile,
        status: PaperlessTaskStatus.Started,
        acknowledged: false,
        task_id: '1237',
        input_data: { filename: 'file4.pdf' },
        date_created: new Date(),
        related_document_ids: [],
      },
      {
        task_type: PaperlessTaskType.ConsumeFile,
        status: PaperlessTaskStatus.Success,
        acknowledged: false,
        task_id: '1238',
        input_data: { filename: 'file5.pdf' },
        date_created: new Date(),
        related_document_ids: [],
      },
    ]

    tasksService.reload()

    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}tasks/?task_type=consume_file&acknowledged=false`
    )

    req.flush(mockTasks)

    expect(tasksService.allFileTasks).toHaveLength(5)
    expect(tasksService.completedFileTasks).toHaveLength(2)
    expect(tasksService.failedFileTasks).toHaveLength(1)
    expect(tasksService.queuedFileTasks).toHaveLength(1)
    expect(tasksService.startedFileTasks).toHaveLength(1)
  })

  it('supports running tasks', () => {
    tasksService.run(PaperlessTaskType.SanityCheck).subscribe((res) => {
      expect(res).toEqual({
        task_id: 'abc-123',
      })
    })
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}tasks/run/`
    )
    expect(req.request.method).toEqual('POST')
    req.flush({
      task_id: 'abc-123',
    })
  })
})
