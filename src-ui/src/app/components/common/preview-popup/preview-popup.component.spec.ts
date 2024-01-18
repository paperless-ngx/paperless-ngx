import { ComponentFixture, TestBed } from '@angular/core/testing'

import { PreviewPopupComponent } from './preview-popup.component'
import { PdfViewerComponent } from '../pdf-viewer/pdf-viewer.component'
import { By } from '@angular/platform-browser'
import { SafeUrlPipe } from 'src/app/pipes/safeurl.pipe'
import { SettingsService } from 'src/app/services/settings.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { DocumentService } from 'src/app/services/rest/document.service'

const doc = {
  id: 10,
  title: 'Document 10',
  content: 'Cupcake ipsum dolor sit amet ice cream.',
  original_file_name: 'sample.pdf',
}

describe('PreviewPopupComponent', () => {
  let component: PreviewPopupComponent
  let fixture: ComponentFixture<PreviewPopupComponent>
  let settingsService: SettingsService
  let documentService: DocumentService

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [PreviewPopupComponent, PdfViewerComponent, SafeUrlPipe],
      imports: [HttpClientTestingModule],
    })
    settingsService = TestBed.inject(SettingsService)
    documentService = TestBed.inject(DocumentService)
    jest
      .spyOn(documentService, 'getPreviewUrl')
      .mockImplementation((id) => doc.original_file_name)
    fixture = TestBed.createComponent(PreviewPopupComponent)
    component = fixture.componentInstance
    component.document = doc
    fixture.detectChanges()
  })

  it('should guess if file is pdf by file name', () => {
    expect(component.isPdf).toBeTruthy()
    component.document.archived_file_name = 'sample.pdf'
    expect(component.isPdf).toBeTruthy()
    component.document.archived_file_name = undefined
    component.document.original_file_name = 'sample.txt'
    expect(component.isPdf).toBeFalsy()
    component.document.original_file_name = 'sample.pdf'
  })

  it('should return settings for native PDF viewer', () => {
    settingsService.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, false)
    expect(component.useNativePdfViewer).toBeFalsy()
    settingsService.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, true)
    expect(component.useNativePdfViewer).toBeTruthy()
  })

  it('should render object if native PDF viewer enabled', () => {
    settingsService.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, true)
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('object'))).not.toBeNull()
  })

  it('should render pngx viewer if native PDF viewer disabled', () => {
    settingsService.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, false)
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('object'))).toBeNull()
    expect(fixture.debugElement.query(By.css('pngx-pdf-viewer'))).not.toBeNull()
  })

  it('should show lock icon on password error', () => {
    settingsService.set(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER, false)
    component.onError({ name: 'PasswordException' })
    fixture.detectChanges()
    expect(component.requiresPassword).toBeTruthy()
    expect(fixture.debugElement.query(By.css('i-bs'))).not.toBeNull()
  })

  it('should fall back to object for non-pdf', () => {
    component.document.original_file_name = 'sample.png'
    fixture.detectChanges()
    expect(fixture.debugElement.query(By.css('object'))).not.toBeNull()
  })

  it('should show message on error', () => {
    component.onError({})
    fixture.detectChanges()
    expect(fixture.debugElement.nativeElement.textContent).toContain(
      'Error loading preview'
    )
  })
})
