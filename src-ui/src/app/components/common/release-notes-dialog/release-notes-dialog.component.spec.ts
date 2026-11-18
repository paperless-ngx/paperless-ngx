import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { PermissionsService } from 'src/app/services/permissions.service'
import { SettingsService } from 'src/app/services/settings.service'
import { environment } from 'src/environments/environment'
import {
  prepareReleaseHtml,
  ReleaseNotesDialogComponent,
} from './release-notes-dialog.component'

describe('ReleaseNotesDialogComponent', () => {
  let component: ReleaseNotesDialogComponent
  let fixture: ComponentFixture<ReleaseNotesDialogComponent>
  let httpTestingController: HttpTestingController
  let settingsService: SettingsService

  function create(updateCheckingEnabled?: boolean, canChangeSettings = true) {
    settingsService = TestBed.inject(SettingsService)
    settingsService.set(SETTINGS_KEYS.VERSION, '3.5.1')
    if (updateCheckingEnabled !== undefined) {
      settingsService.set(
        SETTINGS_KEYS.UPDATE_CHECKING_ENABLED,
        updateCheckingEnabled
      )
    }
    jest
      .spyOn(TestBed.inject(PermissionsService), 'currentUserCan')
      .mockReturnValue(canChangeSettings)
    fixture = TestBed.createComponent(ReleaseNotesDialogComponent)
    component = fixture.componentInstance
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ReleaseNotesDialogComponent],
      providers: [
        DatePipe,
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
    httpTestingController = TestBed.inject(HttpTestingController)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  it('should load and render release notes since a version', () => {
    create(true)
    component.load('3.4.2')
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}release_notes/?since=3.4.2`
    )
    req.flush({
      version: '3.5.1',
      releases: [
        {
          version: '3.5.1',
          name: 'Paperless-ngx v3.5.1',
          body_html:
            '<h2>paperless-ngx 3.5.1</h2><h3>Bug Fixes</h3><ul><li>Fix: a thing</li></ul>' +
            '<h3>All App Changes</h3><details><summary>1 change</summary><ul><li>Fix: a thing</li></ul></details>',
          html_url: '',
          published_at: '2026-11-18T05:22:01Z',
        },
      ],
    })
    fixture.detectChanges()

    const text = fixture.nativeElement.textContent
    expect(text).toContain('Updated from 3.4.2 to 3.5.1')
    expect(text).toContain('Bug Fixes')
    expect(
      fixture.nativeElement.querySelector('.release-notes-body details summary')
        .textContent
    ).toEqual('1 change')
  })

  it('should open release note links safely and drop svg icons', () => {
    const html = prepareReleaseHtml(
      '<div class="markdown-alert"><p class="markdown-alert-title"><svg><path d="M0"></path></svg>Note</p></div>' +
        '<p><a href="https://github.com/paperless-ngx/paperless-ngx/pull/1" data-hovercard-type="pull_request">#1</a></p>'
    )
    const doc = new DOMParser().parseFromString(html, 'text/html')
    expect(doc.querySelector('svg')).toBeNull()
    expect(doc.querySelector('.markdown-alert-title').textContent).toEqual(
      'Note'
    )
    const link = doc.querySelector('a')
    expect(link.getAttribute('target')).toEqual('_blank')
    expect(link.getAttribute('rel')).toEqual('noopener noreferrer nofollow')
    expect(link.hasAttribute('data-hovercard-type')).toBe(false)
  })

  it('should show a message if release notes could not be loaded', () => {
    create(true)
    component.load(null)
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}release_notes/`)
      .flush('error', { status: 500, statusText: 'error' })
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain(
      'Release notes could not be loaded'
    )
  })

  it('should not fetch release notes if update checking is disabled', () => {
    create(false)
    component.load('3.4.2')
    fixture.detectChanges()

    httpTestingController.expectNone(`${environment.apiBaseUrl}release_notes/`)
    expect(fixture.nativeElement.textContent).toContain(
      'when update checking is enabled'
    )
    expect(component.releaseUrl).toEqual(
      'https://github.com/paperless-ngx/paperless-ngx/releases/tag/v3.5.1'
    )
  })

  it('should offer to enable update checking if never chosen', () => {
    create()
    const chosen = jest.fn()
    component.updateCheckingChosen.subscribe(chosen)
    component.load('3.4.2')
    fixture.detectChanges()

    const enable = Array.from(
      fixture.nativeElement.querySelectorAll('.modal-body button')
    ).find((b: HTMLButtonElement) => b.textContent.trim() === 'Enable') as
      HTMLButtonElement | undefined
    expect(enable).toBeTruthy()
    httpTestingController.expectNone(`${environment.apiBaseUrl}release_notes/`)

    enable.click()
    expect(chosen).toHaveBeenCalledWith(true)
    httpTestingController
      .expectOne(`${environment.apiBaseUrl}release_notes/?since=3.4.2`)
      .flush({ version: '3.5.1', releases: [] })
  })

  it('should show the disabled message after choosing disable', () => {
    create()
    const chosen = jest.fn()
    component.updateCheckingChosen.subscribe(chosen)
    component.load(null)
    component.setUpdateChecking(false)
    fixture.detectChanges()

    expect(chosen).toHaveBeenCalledWith(false)
    httpTestingController.expectNone(`${environment.apiBaseUrl}release_notes/`)
    expect(fixture.nativeElement.textContent).toContain(
      'when update checking is enabled'
    )
  })

  it('should not offer to enable update checking without permission', () => {
    create(undefined, false)
    component.load(null)
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).not.toContain('Enable')
    expect(fixture.nativeElement.textContent).toContain(
      'when update checking is enabled'
    )
  })

  it('should support close', () => {
    create(false)
    const closeSpy = jest.spyOn(component.activeModal, 'close')
    component.close()
    expect(closeSpy).toHaveBeenCalled()
  })
})
