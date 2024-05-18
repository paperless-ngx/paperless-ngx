import { TestBed } from '@angular/core/testing'
import { TasksService } from './tasks.service'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'
import { PaperlessTaskType } from '../data/paperless-task'
import { PaperlessTaskStatus } from '../data/paperless-task'

describe('TasksService', () => {
  let httpTestingController: HttpTestingController
  let tasksService: TasksService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [TasksService],
      imports: [HttpClientTestingModule],
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
      `${environment.apiBaseUrl}tasks/`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('calls acknowledge_tasks api endpoint on dismiss and reloads', () => {
    tasksService.dismissTasks(new Set([1, 2, 3]))
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}acknowledge_tasks/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({
      tasks: [1, 2, 3],
    })
    req.flush([])
    // reload is then called
    httpTestingController.expectOne(`${environment.apiBaseUrl}tasks/`).flush([])
  })

  it('sorts tasks returned from api', () => {
    expect(tasksService.total).toEqual(0)
    const mockTasks = [
      {
        type: PaperlessTaskType.File,
        status: PaperlessTaskStatus.Complete,
        acknowledged: false,
        task_id: '1234',
        task_file_name: 'file1.pdf',
        date_created: new Date(),
      },
      {
        type: PaperlessTaskType.File,
        status: PaperlessTaskStatus.Failed,
        acknowledged: false,
        task_id: '1235',
        task_file_name: 'file2.pdf',
        date_created: new Date(),
      },
      {
        type: PaperlessTaskType.File,
        status: PaperlessTaskStatus.Pending,
        acknowledged: false,
        task_id: '1236',
        task_file_name: 'file3.pdf',
        date_created: new Date(),
      },
      {
        type: PaperlessTaskType.File,
        status: PaperlessTaskStatus.Started,
        acknowledged: false,
        task_id: '1237',
        task_file_name: 'file4.pdf',
        date_created: new Date(),
      },
      {
        type: PaperlessTaskType.File,
        status: PaperlessTaskStatus.Complete,
        acknowledged: false,
        task_id: '1238',
        task_file_name: 'file5.pdf',
        date_created: new Date(),
      },
    ]

    tasksService.reload()

    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}tasks/`
    )

    req.flush(mockTasks)

    expect(tasksService.allFileTasks).toHaveLength(5)
    expect(tasksService.completedFileTasks).toHaveLength(2)
    expect(tasksService.failedFileTasks).toHaveLength(1)
    expect(tasksService.queuedFileTasks).toHaveLength(1)
    expect(tasksService.startedFileTasks).toHaveLength(1)
  })
})
