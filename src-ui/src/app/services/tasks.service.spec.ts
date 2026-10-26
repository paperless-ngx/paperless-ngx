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
import { PaperlessTaskType } from '../data/paperless-task'
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

  it('calls tasks status counts api endpoint on reload', () => {
    tasksService.reload()
    const req = httpTestingController.expectOne(
      (req: HttpRequest<unknown>) =>
        req.url === `${environment.apiBaseUrl}tasks/status_counts/` &&
        req.params.get('acknowledged') === 'false'
    )
    expect(req.request.method).toEqual('GET')
    req.flush({ all: 0, needs_attention: 3, in_progress: 0, completed: 0 })
    expect(tasksService.needsAttentionTasksCount).toEqual(3)
  })

  it('cancels an in-progress reload when reloading again', () => {
    tasksService.reload()
    const staleReload = httpTestingController.expectOne(
      (req: HttpRequest<unknown>) =>
        req.url === `${environment.apiBaseUrl}tasks/status_counts/`
    )
    tasksService.reload()

    expect(staleReload.cancelled).toBe(true)
    httpTestingController
      .expectOne(
        (req: HttpRequest<unknown>) =>
          req.url === `${environment.apiBaseUrl}tasks/status_counts/`
      )
      .flush({ all: 0, needs_attention: 0, in_progress: 0, completed: 0 })
  })

  it('continues reloading after a reload request fails', () => {
    tasksService.reload()
    httpTestingController
      .expectOne(
        (req: HttpRequest<unknown>) =>
          req.url === `${environment.apiBaseUrl}tasks/status_counts/`
      )
      .flush('error', { status: 500, statusText: 'error' })

    expect(tasksService.loading).toBe(false)

    tasksService.reload()
    httpTestingController
      .expectOne(
        (req: HttpRequest<unknown>) =>
          req.url === `${environment.apiBaseUrl}tasks/status_counts/`
      )
      .flush({ all: 0, needs_attention: 0, in_progress: 0, completed: 0 })
  })

  it('reloads after dismissing a task while a reload is already in progress', () => {
    tasksService.reload()
    const staleReload = httpTestingController.expectOne(
      (req: HttpRequest<unknown>) =>
        req.url === `${environment.apiBaseUrl}tasks/status_counts/` &&
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
          req.url === `${environment.apiBaseUrl}tasks/status_counts/` &&
          req.params.get('acknowledged') === 'false'
      )
      .flush({ all: 0, needs_attention: 42, in_progress: 0, completed: 0 })

    expect(tasksService.needsAttentionTasksCount).toEqual(42)
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
          req.url === `${environment.apiBaseUrl}tasks/status_counts/` &&
          req.params.get('acknowledged') === 'false'
      )
      .flush({ all: 0, needs_attention: 0, in_progress: 0, completed: 0 })
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
          req.url === `${environment.apiBaseUrl}tasks/status_counts/` &&
          req.params.get('acknowledged') === 'false'
      )
      .flush({ all: 0, needs_attention: 0, in_progress: 0, completed: 0 })
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
