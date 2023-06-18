import { TestBed } from '@angular/core/testing'
import { SettingsService } from './settings.service'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { RouterTestingModule } from '@angular/router/testing'
import { environment } from 'src/environments/environment'
import { Subscription } from 'rxjs'
import { PaperlessUiSettings } from '../data/paperless-uisettings'
import { SETTINGS_KEYS } from '../data/paperless-uisettings'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { AppModule } from '../app.module'

describe('SettingsService', () => {
  let httpTestingController: HttpTestingController
  let settingsService: SettingsService
  let subscription: Subscription

  const ui_settings: PaperlessUiSettings = {
    user: {
      username: 'testuser',
      first_name: 'Test',
      last_name: 'User',
      id: 1,
      is_superuser: true,
    },
    settings: {
      language: '',
      bulk_edit: { confirmation_dialogs: true, apply_on_close: false },
      documentListSize: 50,
      dark_mode: { use_system: true, enabled: 'false', thumb_inverted: 'true' },
      theme: { color: '#9fbf2f' },
      document_details: { native_pdf_viewer: false },
      date_display: { date_locale: '', date_format: 'mediumDate' },
      notifications: {
        consumer_new_documents: true,
        consumer_success: true,
        consumer_failed: true,
        consumer_suppress_on_dashboard: true,
      },
      comments_enabled: true,
      slim_sidebar: false,
      update_checking: { enabled: false, backend_setting: 'default' },
      saved_views: { warn_on_unsaved_change: true },
      notes_enabled: true,
      tour_complete: false,
    },
    permissions: [],
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [],
      providers: [SettingsService],
      imports: [
        HttpClientTestingModule,
        RouterTestingModule,
        NgbModule,
        FormsModule,
        ReactiveFormsModule,
        AppModule,
      ],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    settingsService = TestBed.inject(SettingsService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('calls ui_settings api endpoint on initialize', () => {
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}ui_settings/`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('calls ui_settings api endpoint with POST on store', () => {
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}ui_settings/`
    )
    req.flush(ui_settings)

    subscription = settingsService.storeSettings().subscribe()
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}ui_settings/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({
      settings: ui_settings.settings,
    })
  })

  it('correctly loads settings of various types', () => {
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}ui_settings/`
    )
    req.flush(ui_settings)

    expect(settingsService.displayName).toEqual('Test')
    expect(settingsService.getLanguage()).toEqual('')
    expect(settingsService.get(SETTINGS_KEYS.DARK_MODE_ENABLED)).toBeFalsy()
    expect(
      settingsService.get(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT)
    ).toBeTruthy()
    expect(settingsService.get(SETTINGS_KEYS.DOCUMENT_LIST_SIZE)).toEqual(50)
    expect(settingsService.get(SETTINGS_KEYS.THEME_COLOR)).toEqual('#9fbf2f')
  })

  it('correctly allows updating settings of various types', () => {
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}ui_settings/`
    )
    req.flush(ui_settings)

    settingsService.setLanguage('de-de')
    settingsService.set(SETTINGS_KEYS.DARK_MODE_ENABLED, true)
    settingsService.set(
      SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT,
      false
    )
    settingsService.set(SETTINGS_KEYS.DOCUMENT_LIST_SIZE, 25)
    settingsService.set(SETTINGS_KEYS.THEME_COLOR, '#000000')

    expect(settingsService.getLanguage()).toEqual('de-de')
    expect(settingsService.get(SETTINGS_KEYS.DARK_MODE_ENABLED)).toBeTruthy()
    expect(
      settingsService.get(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT)
    ).toBeFalsy()
    expect(settingsService.get(SETTINGS_KEYS.DOCUMENT_LIST_SIZE)).toEqual(25)
    expect(settingsService.get(SETTINGS_KEYS.THEME_COLOR)).toEqual('#000000')
  })

  it('updates appearnce settings', () => {
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}ui_settings/`
    )
    req.flush(ui_settings)

    expect(
      document.body.style.getPropertyValue('--pngx-primary-lightness')
    ).toEqual('')

    const addClassSpy = jest.spyOn(settingsService.renderer, 'addClass')
    const removeClassSpy = jest.spyOn(settingsService.renderer, 'removeClass')

    settingsService.updateAppearanceSettings(true, true, '#fff000')
    expect(addClassSpy).toHaveBeenCalledWith(document.body, 'primary-light')
    expect(addClassSpy).toHaveBeenCalledWith(
      document.body,
      'color-scheme-system'
    )
    expect(
      document.body.style.getPropertyValue('--pngx-primary-lightness')
    ).toEqual('50%')

    settingsService.updateAppearanceSettings(false, false, '#000000')
    expect(addClassSpy).toHaveBeenCalledWith(document.body, 'primary-light')
    expect(removeClassSpy).toHaveBeenCalledWith(
      document.body,
      'color-scheme-system'
    )
    expect(
      document.body.style.getPropertyValue('--pngx-primary-lightness')
    ).toEqual('0%')

    settingsService.updateAppearanceSettings(false, true, '#ffffff')
    expect(addClassSpy).toHaveBeenCalledWith(document.body, 'primary-dark')
    expect(removeClassSpy).toHaveBeenCalledWith(
      document.body,
      'color-scheme-system'
    )
    expect(addClassSpy).toHaveBeenCalledWith(document.body, 'color-scheme-dark')
    expect(
      document.body.style.getPropertyValue('--pngx-primary-lightness')
    ).toEqual('100%')
  })

  it('migrates settings automatically', () => {
    const oldSettings = Object.assign({}, ui_settings)
    delete oldSettings.settings['documentListSize']
    window.localStorage.setItem(SETTINGS_KEYS.DOCUMENT_LIST_SIZE, '50')
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}ui_settings/`
    )
    req.flush(oldSettings)

    req = httpTestingController.match(
      `${environment.apiBaseUrl}ui_settings/`
    )[0]
    expect(req.request.method).toEqual('POST')
  })

  it('updates settings on complete tour', () => {
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}ui_settings/`
    )
    req.flush(ui_settings)

    settingsService.completeTour()

    req = httpTestingController.match(
      `${environment.apiBaseUrl}ui_settings/`
    )[0]
    expect(req.request.method).toEqual('POST')
  })
})
