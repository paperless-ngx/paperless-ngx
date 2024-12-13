import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  discardPeriodicTasks,
  fakeAsync,
  flush,
  tick,
} from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { NgxFileDropEntry, NgxFileDropModule } from 'ngx-file-drop'
import { PermissionsService } from 'src/app/services/permissions.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { UploadDocumentsService } from 'src/app/services/upload-documents.service'
import { ToastsComponent } from '../common/toasts/toasts.component'
import { FileDropComponent } from './file-drop.component'

describe('FileDropComponent', () => {
  let component: FileDropComponent
  let fixture: ComponentFixture<FileDropComponent>
  let permissionsService: PermissionsService
  let toastService: ToastService
  let settingsService: SettingsService
  let uploadDocumentsService: UploadDocumentsService

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [FileDropComponent, ToastsComponent],
      imports: [NgxFileDropModule],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    permissionsService = TestBed.inject(PermissionsService)
    settingsService = TestBed.inject(SettingsService)
    toastService = TestBed.inject(ToastService)
    uploadDocumentsService = TestBed.inject(UploadDocumentsService)

    fixture = TestBed.createComponent(FileDropComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should enable drag-drop if user has permissions', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    expect(component.dragDropEnabled).toBeTruthy()
  })

  it('should disable drag-drop if user does not have permissions', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(false)
    expect(component.dragDropEnabled).toBeFalsy()
  })

  it('should disable drag-drop if disabled in settings', fakeAsync(() => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    settingsService.globalDropzoneEnabled = false
    expect(component.dragDropEnabled).toBeFalsy()

    component.onDragOver(new Event('dragover') as DragEvent)
    tick(1)
    fixture.detectChanges()
    expect(component.fileIsOver).toBeFalsy()
    const dropzone = fixture.debugElement.query(
      By.css('.global-dropzone-overlay')
    )
    expect(dropzone.classes['hide']).toBeTruthy()
    component.onDragLeave(new Event('dragleave') as DragEvent)
    tick(700)
    fixture.detectChanges()
    // drop
    const uploadSpy = jest.spyOn(uploadDocumentsService, 'uploadFiles')
    const dragEvent = new Event('drop')
    dragEvent['dataTransfer'] = {
      files: {
        item: () => {},
        length: 0,
      },
    }
    component.onDrop(dragEvent as DragEvent)
    tick(3000)
    expect(uploadSpy).not.toHaveBeenCalled()
  }))

  it('should support drag drop, initiate upload', fakeAsync(() => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    expect(component.fileIsOver).toBeFalsy()
    const overEvent = new Event('dragover') as DragEvent
    ;(overEvent as any).dataTransfer = { types: ['Files'] }
    component.onDragOver(overEvent)
    tick(1)
    fixture.detectChanges()
    expect(component.fileIsOver).toBeTruthy()
    const dropzone = fixture.debugElement.query(
      By.css('.global-dropzone-overlay')
    )
    component.onDragLeave(new Event('dragleave') as DragEvent)
    tick(700)
    fixture.detectChanges()
    expect(dropzone.classes['hide']).toBeTruthy()
    // drop
    const toastSpy = jest.spyOn(toastService, 'show')
    const uploadSpy = jest.spyOn(
      UploadDocumentsService.prototype as any,
      'uploadFile'
    )
    const dragEvent = new Event('drop')
    dragEvent['dataTransfer'] = {
      files: {
        item: () => {
          return new File(
            [new Blob(['testing'], { type: 'application/pdf' })],
            'file.pdf'
          )
        },
        length: 1,
      } as unknown as FileList,
    }
    component.onDrop(dragEvent as DragEvent)
    component.dropped([
      {
        fileEntry: {
          isFile: true,
          file: (callback) => {
            callback(
              new File(
                [new Blob(['testing'], { type: 'application/pdf' })],
                'file.pdf'
              )
            )
          },
        },
      } as unknown as NgxFileDropEntry,
    ])
    tick(3000)
    expect(toastSpy).toHaveBeenCalled()
    expect(uploadSpy).toHaveBeenCalled()
    discardPeriodicTasks()
  }))

  it('should ignore events if disabled', fakeAsync(() => {
    settingsService.globalDropzoneEnabled = false
    expect(settingsService.globalDropzoneActive).toBeFalsy()
    component.onDragOver(new Event('dragover') as DragEvent)
    expect(settingsService.globalDropzoneActive).toBeFalsy()
    settingsService.globalDropzoneActive = true
    component.onDragLeave(new Event('dragleave') as DragEvent)
    expect(settingsService.globalDropzoneActive).toBeTruthy()
    component.onDrop(new Event('drop') as DragEvent)
    expect(settingsService.globalDropzoneActive).toBeTruthy()
  }))

  it('should hide if app loses focus', fakeAsync(() => {
    const leaveSpy = jest.spyOn(component, 'onDragLeave')
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    settingsService.globalDropzoneEnabled = true
    const overEvent = new Event('dragover') as DragEvent
    ;(overEvent as any).dataTransfer = { types: ['Files'] }
    component.onDragOver(overEvent)
    tick(1)
    expect(component.hidden).toBeFalsy()
    expect(component.fileIsOver).toBeTruthy()
    jest.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    component.onVisibilityChange()
    expect(leaveSpy).toHaveBeenCalled()
    flush()
  }))

  it('should hide on window blur', fakeAsync(() => {
    const leaveSpy = jest.spyOn(component, 'onDragLeave')
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    settingsService.globalDropzoneEnabled = true
    const overEvent = new Event('dragover') as DragEvent
    ;(overEvent as any).dataTransfer = { types: ['Files'] }
    component.onDragOver(overEvent)
    tick(1)
    expect(component.hidden).toBeFalsy()
    expect(component.fileIsOver).toBeTruthy()
    jest.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    component.onWindowBlur()
    expect(leaveSpy).toHaveBeenCalled()
    flush()
  }))
})
