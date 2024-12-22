import { ComponentFixture, TestBed } from '@angular/core/testing'

import {
  HttpClient,
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { By } from '@angular/platform-browser'
import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import { PdfViewerModule } from 'ng2-pdf-viewer'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { SafeUrlPipe } from 'src/app/pipes/safeurl.pipe'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { PreviewPopupComponent } from './preview-popup.component'

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
    jest.useFakeTimers()
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

  it('should show preview on mouseover after delay to preload content', () => {
    component.mouseEnterPreview()
    expect(component.popover.isOpen()).toBeTruthy()
    jest.advanceTimersByTime(600)
    component.close()
    jest.advanceTimersByTime(600)
  })

  it('should not show preview on mouseover if mouse no longer on preview', () => {
    component.mouseEnterPreview()
    jest.advanceTimersByTime(100)
    component.mouseLeavePreview()
    jest.advanceTimersByTime(600)
    expect(component.popover.isOpen()).toBeFalsy()
  })

  it('should not close preview on mouseleave if mouse back on preview', () => {
    component.close()
    component.mouseEnterPreview()
    jest.advanceTimersByTime(300)
    expect(component.popover.isOpen()).toBeTruthy()
  })

  it('should support immediate close on mouseleave', () => {
    component.mouseEnterPreview()
    jest.advanceTimersByTime(600)
    expect(component.popover.isOpen()).toBeTruthy()
    component.mouseLeavePreview()
    component.close(true)
    jest.advanceTimersByTime(1)
    expect(component.popover.isOpen()).toBeFalsy()
  })
})
