import {
  HttpRequest,
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import {
  PaperlessTaskStatus,
  PaperlessTaskTriggerSource,
  PaperlessTaskType,
} from '../data/paperless-task'
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
      (req: HttpRequest<unknown>) =>
        req.url === `${environment.apiBaseUrl}tasks/` &&
        req.params.get('acknowledged') === 'false' &&
        req.params.get('page_size') === '1000'
    )
    expect(req.request.method).toEqual('GET')
    req.flush({ count: 0, results: [] })
  })

  it('cancels an in-progress reload when reloading again', () => {
    tasksService.reload()
    const staleReload = httpTestingController.expectOne(
      (req: HttpRequest<unknown>) =>
        req.url === `${environment.apiBaseUrl}tasks/`
    )
    tasksService.reload()

    expect(staleReload.cancelled).toBe(true)
    httpTestingController
      .expectOne(
        (req: HttpRequest<unknown>) =>
          req.url === `${environment.apiBaseUrl}tasks/`
      )
      .flush({ count: 0, results: [] })
  })

  it('continues reloading after a reload request fails', () => {
    tasksService.reload()
    httpTestingController
      .expectOne(
        (req: HttpRequest<unknown>) =>
          req.url === `${environment.apiBaseUrl}tasks/`
      )
      .flush('error', { status: 500, statusText: 'error' })

    expect(tasksService.loading).toBe(false)

    tasksService.reload()
    httpTestingController
      .expectOne(
        (req: HttpRequest<unknown>) =>
          req.url === `${environment.apiBaseUrl}tasks/`
      )
      .flush({ count: 0, results: [] })
  })

  it('reloads after dismissing a task while a reload is already in progress', () => {
    tasksService.reload()
    const staleReload = httpTestingController.expectOne(
      (req: HttpRequest<unknown>) =>
        req.url === `${environment.apiBaseUrl}tasks/` &&
        req.params.get('acknowledged') === 'false'
    )

    tasksService.dismissTasks(new Set([1])).subscribe()
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}tasks/acknowledge/`)
      .flush([])

    expect(staleReload.cancelled).toBe(true)
    httpTestingController
      .expectOne(
        (req: HttpRequest<unknown>) =>
          req.url === `${environment.apiBaseUrl}tasks/` &&
          req.params.get('acknowledged') === 'false'
      )
      .flush({ count: 0, results: [] })

    expect(tasksService.needsAttentionTasks).toHaveLength(0)
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
        (req: HttpRequest<unknown>) =>
          req.url === `${environment.apiBaseUrl}tasks/` &&
          req.params.get('acknowledged') === 'false' &&
          req.params.get('page_size') === '1000'
      )
      .flush({ count: 0, results: [] })
  })

  it('calls acknowledge_tasks api endpoint on dismiss all and reloads', () => {
    tasksService.dismissAllTasks().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}tasks/acknowledge/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({
      all: true,
    })
    req.flush([])
    // reload is then called
    httpTestingController
      .expectOne(
        (req: HttpRequest<unknown>) =>
          req.url === `${environment.apiBaseUrl}tasks/` &&
          req.params.get('acknowledged') === 'false' &&
          req.params.get('page_size') === '1000'
      )
      .flush({ count: 0, results: [] })
  })

  it('includes revoked tasks in needs attention', () => {
    const mockTasks = [
      {
        task_type: PaperlessTaskType.SanityCheck,
        trigger_source: PaperlessTaskTriggerSource.System,
        status: PaperlessTaskStatus.Failure,
        acknowledged: false,
        task_id: '1235',
        input_data: {},
        date_created: new Date(),
        related_document_ids: [],
      },
      {
        task_type: PaperlessTaskType.MailFetch,
        trigger_source: PaperlessTaskTriggerSource.Scheduled,
        status: PaperlessTaskStatus.Revoked,
        acknowledged: false,
        task_id: '1236',
        input_data: {},
        date_created: new Date(),
        related_document_ids: [],
      },
      {
        task_type: PaperlessTaskType.EmptyTrash,
        trigger_source: PaperlessTaskTriggerSource.Manual,
        status: PaperlessTaskStatus.Success,
        acknowledged: false,
        task_id: '1238',
        input_data: {},
        date_created: new Date(),
        related_document_ids: [],
      },
    ]

    tasksService.reload()

    const req = httpTestingController.expectOne(
      (req: HttpRequest<unknown>) =>
        req.url === `${environment.apiBaseUrl}tasks/` &&
        req.params.get('acknowledged') === 'false' &&
        req.params.get('page_size') === '1000'
    )

    req.flush({ count: mockTasks.length, results: mockTasks })

    expect(tasksService.needsAttentionTasks).toHaveLength(2)
    expect(tasksService.needsAttentionTasks.map((task) => task.status)).toEqual(
      expect.arrayContaining([
        PaperlessTaskStatus.Failure,
        PaperlessTaskStatus.Revoked,
      ])
    )
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

  it('loads filtered task status counts', () => {
    tasksService
      .statusCounts({
        acknowledged: false,
        task_type: PaperlessTaskType.ConsumeFile,
      })
      .subscribe((res) => {
        expect(res).toEqual({
          all: 10,
          needs_attention: 2,
          in_progress: 3,
          completed: 5,
        })
      })

    const req = httpTestingController.expectOne(
      (req: HttpRequest<unknown>) =>
        req.url === `${environment.apiBaseUrl}tasks/status_counts/` &&
        req.params.get('acknowledged') === 'false' &&
        req.params.get('task_type') === PaperlessTaskType.ConsumeFile
    )
    expect(req.request.method).toEqual('GET')
    req.flush({
      all: 10,
      needs_attention: 2,
      in_progress: 3,
      completed: 5,
    })
  })
})
