import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { LogService } from 'src/app/services/rest/log.service'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LogsComponent } from './logs.component'
import { of, throwError } from 'rxjs'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { NgbModule, NgbNavLink } from '@ng-bootstrap/ng-bootstrap'
import { BrowserModule, By } from '@angular/platform-browser'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'

const edoc_logs = [
  '[2023-05-29 03:05:01,224] [DEBUG] [edoc.tasks] Training data unchanged.',
  '[2023-05-29 04:05:00,622] [DEBUG] [edoc.classifier] Gathering data from database...',
  '[2023-05-29 04:05:01,213] [DEBUG] [edoc.tasks] Training data unchanged.',
  '[2023-06-11 00:30:01,774] [INFO] [edoc.sanity_checker] Document contains no OCR data',
  '[2023-06-11 00:30:01,774] [WARNING] [edoc.sanity_checker] Made up',
  '[2023-06-11 00:30:01,774] [ERROR] [edoc.sanity_checker] Document contains no OCR data',
  '[2023-06-11 00:30:01,774] [CRITICAL] [edoc.sanity_checker] Document contains no OCR data',
]
const mail_logs = [
  '[2023-06-09 01:10:00,666] [DEBUG] [edoc_mail] Rule inbox@example.com.Incoming: Searching folder with criteria (SINCE 10-May-2023 UNSEEN)',
  '[2023-06-09 01:10:01,385] [DEBUG] [edoc_mail] Rule inbox@example.com.Incoming: Processed 3 matching mail(s)',
]

describe('LogsComponent', () => {
  let component: LogsComponent
  let fixture: ComponentFixture<LogsComponent>
  let logService: LogService
  let logSpy
  let reloadSpy

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [LogsComponent, PageHeaderComponent],
      providers: [],
      imports: [
        HttpClientTestingModule,
        BrowserModule,
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    logService = TestBed.inject(LogService)
    jest.spyOn(logService, 'list').mockReturnValue(of(['edoc', 'mail']))
    logSpy = jest.spyOn(logService, 'get')
    logSpy.mockImplementation((id) => {
      return of(id === 'edoc' ? edoc_logs : mail_logs)
    })
    fixture = TestBed.createComponent(LogsComponent)
    component = fixture.componentInstance
    reloadSpy = jest.spyOn(component, 'reloadLogs')
    window.HTMLElement.prototype.scroll = function () {} // mock scroll
    jest.useFakeTimers()
    fixture.detectChanges()
  })

  it('should display logs with first log initially', () => {
    expect(logSpy).toHaveBeenCalledWith('edoc')
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      edoc_logs[0]
    )
  })

  it('should load log when tab clicked', () => {
    fixture.debugElement
      .queryAll(By.directive(NgbNavLink))[1]
      .nativeElement.dispatchEvent(new MouseEvent('click'))
    expect(logSpy).toHaveBeenCalledWith('mail')
  })

  it('should handle error with no logs', () => {
    logSpy.mockReturnValueOnce(
      throwError(() => new Error('error getting logs'))
    )
    component.reloadLogs()
    expect(component.logs).toHaveLength(0)
  })

  it('should auto refresh, allow toggle', () => {
    jest.advanceTimersByTime(6000)
    expect(reloadSpy).toHaveBeenCalledTimes(2)

    component.toggleAutoRefresh()
    expect(component.autoRefreshInterval).toBeNull()
    jest.advanceTimersByTime(6000)
    expect(reloadSpy).toHaveBeenCalledTimes(2)
  })
})
