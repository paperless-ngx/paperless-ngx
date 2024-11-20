import {
  ComponentFixture,
  fakeAsync,
  TestBed,
  tick,
} from '@angular/core/testing'

import { PreviewPopupComponent } from './preview-popup.component'
import { By } from '@angular/platform-browser'
import { SafeUrlPipe } from 'src/app/pipes/safeurl.pipe'
import { SettingsService } from 'src/app/services/settings.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { DocumentService } from 'src/app/services/rest/document.service'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { PdfViewerModule } from 'ng2-pdf-viewer'
import {
  HttpClient,
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http'
import { of, throwError } from 'rxjs'
import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'

const doc = {
  id: 10,
  title: 'Document 10',
  content: 'Cupcake ipsum dolor sit amet ice cream.',
  original_file_name: 'sample.pdf',
  archived_file_name: 'sample.pdf',
  mime_type: 'application/pdf',
}

describe('PreviewPopupComponent', () => {
  let component: PreviewPopupComponent
  let fixture: ComponentFixture<PreviewPopupComponent>
  let settingsService: SettingsService
  let documentService: DocumentService
  let http: HttpClient

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [PreviewPopupComponent, SafeUrlPipe, DocumentTitlePipe],
      imports: [
        NgxBootstrapIconsModule.pick(allIcons),
        PdfViewerModule,
        NgbPopoverModule,
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
    settingsService = TestBed.inject(SettingsService)
    documentService = TestBed.inject(DocumentService)
    http = TestBed.inject(HttpClient)
    jest
      .spyOn(documentService, 'getPreviewUrl')
      .mockImplementation((id) => doc.original_file_name)
    fixture = TestBed.createComponent(PreviewPopupComponent)
    component = fixture.componentInstance
    component.document = { ...doc }
    fixture.detectChanges()
  })

  it('should correctly report if document is pdf', () => {
    expect(component.isPdf).toBeTruthy()
    component.document.mime_type = 'application/msword'
    expect(component.isPdf).toBeTruthy() // still has archive file
    component.document.archived_file_name = undefined
    expect(component.isPdf).toBeFalsy()
  })

  it('should return settings for native PDF viewer', () => {
    settingsService.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, false)
    expect(component.useNativePdfViewer).toBeFalsy()
    settingsService.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, true)
    expect(component.useNativePdfViewer).toBeTruthy()
  })

  it('should render object if native PDF viewer enabled', () => {
    settingsService.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, true)
    component.popover.open()
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('object'))).not.toBeNull()
  })

  it('should render pngx viewer if native PDF viewer disabled', () => {
    settingsService.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, false)
    component.popover.open()
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('object'))).toBeNull()
    expect(fixture.debugElement.query(By.css('pdf-viewer'))).not.toBeNull()
  })

  it('should show lock icon on password error', () => {
    settingsService.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, false)
    component.popover.open()
    component.onError({ name: 'PasswordException' })
    fixture.detectChanges()
    expect(component.requiresPassword).toBeTruthy()
    expect(fixture.debugElement.query(By.css('i-bs'))).not.toBeNull()
  })

  it('should fall back to object for non-pdf', () => {
    component.document.original_file_name = 'sample.png'
    component.document.mime_type = 'image/png'
    component.document.archived_file_name = undefined
    component.popover.open()
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('object'))).not.toBeNull()
  })

  it('should show message on error', () => {
    component.popover.open()
    component.onError({})
    fixture.detectChanges()
    expect(
      fixture.debugElement.query(By.css('.popover')).nativeElement.textContent
    ).toContain('Error loading preview')
  })

  it('should get text content from http if appropriate', () => {
    component.document = {
      ...doc,
      original_file_name: 'sample.txt',
      mime_type: 'text/plain',
    }
    const httpSpy = jest.spyOn(http, 'get')
    httpSpy.mockReturnValueOnce(
      throwError(() => new Error('Error getting preview'))
    )
    component.init()
    expect(httpSpy).toHaveBeenCalled()
    expect(component.error).toBeTruthy()
    httpSpy.mockReturnValueOnce(of('Preview text'))
    component.init()
    expect(component.previewText).toEqual('Preview text')
  })

  it('should show preview on mouseover after delay to preload content', fakeAsync(() => {
    component.mouseEnterPreview()
    expect(component.popover.isOpen()).toBeTruthy()
    tick(600)
    component.close()

    component.mouseEnterPreview()
    tick(100)
    component.mouseLeavePreview()
    tick(600)
    expect(component.popover.isOpen()).toBeFalsy()
  }))
})
