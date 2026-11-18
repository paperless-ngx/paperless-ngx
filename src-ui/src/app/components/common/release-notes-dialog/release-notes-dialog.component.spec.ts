import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { SettingsService } from 'src/app/services/settings.service'
import { environment } from 'src/environments/environment'
import { ReleaseNotesDialogComponent } from './release-notes-dialog.component'

describe('ReleaseNotesDialogComponent', () => {
  let component: ReleaseNotesDialogComponent
  let fixture: ComponentFixture<ReleaseNotesDialogComponent>
  let httpTestingController: HttpTestingController
  let settingsService: SettingsService

  function create(updateCheckingEnabled: boolean) {
    settingsService = TestBed.inject(SettingsService)
    settingsService.set(SETTINGS_KEYS.VERSION, '3.5.1')
    settingsService.set(
      SETTINGS_KEYS.UPDATE_CHECKING_ENABLED,
      updateCheckingEnabled
    )
    fixture = TestBed.createComponent(ReleaseNotesDialogComponent)
    component = fixture.componentInstance
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ReleaseNotesDialogComponent],
      providers: [
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
          body: '## paperless-ngx 3.5.1\r\n\r\n### Bug Fixes\r\n\r\n- Fix: a thing ([#1](https://github.com/paperless-ngx/paperless-ngx/pull/1))',
          html_url: '',
          published_at: '',
        },
      ],
    })
    fixture.detectChanges()

    const text = fixture.nativeElement.textContent
    expect(text).toContain('Updated from 3.4.2 to 3.5.1')
    expect(text).toContain('Bug Fixes')
    expect(text).not.toContain('paperless-ngx 3.5.1')
    expect(text).not.toContain('(github.com)')
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

  it('should support close', () => {
    create(false)
    const closeSpy = jest.spyOn(component.activeModal, 'close')
    component.close()
    expect(closeSpy).toHaveBeenCalled()
  })
})
