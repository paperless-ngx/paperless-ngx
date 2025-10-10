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
      imports: [FileDropComponent, ToastsComponent],
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
    expect(dropzone.classes['active']).toBeFalsy()
    component.onDragLeave(new Event('dragleave') as DragEvent)
    tick(700)
    fixture.detectChanges()
    // drop
    const uploadSpy = jest.spyOn(uploadDocumentsService, 'uploadFile')
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
    component.onDragLeave(new Event('dragleave') as DragEvent)
    tick(700)
    fixture.detectChanges()
    // drop
    const toastSpy = jest.spyOn(toastService, 'show')
    const uploadSpy = jest.spyOn(uploadDocumentsService, 'uploadFile')
    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    const dragEvent = new Event('drop')
    dragEvent['dataTransfer'] = {
      items: [
        {
          kind: 'file',
          type: 'application/pdf',
          getAsFile: () => file,
        },
      ],
    }
    component.onDrop(dragEvent as DragEvent)
    tick(3000)
    expect(toastSpy).toHaveBeenCalled()
    expect(uploadSpy).toHaveBeenCalled()
    discardPeriodicTasks()
  }))

  it('should support drag drop, initiate upload with webkitGetAsEntry', fakeAsync(() => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    expect(component.fileIsOver).toBeFalsy()
    const overEvent = new Event('dragover') as DragEvent
    ;(overEvent as any).dataTransfer = { types: ['Files'] }
    component.onDragOver(overEvent)
    tick(1)
    fixture.detectChanges()
    expect(component.fileIsOver).toBeTruthy()
    component.onDragLeave(new Event('dragleave') as DragEvent)
    tick(700)
    fixture.detectChanges()
    // drop
    const toastSpy = jest.spyOn(toastService, 'show')
    const uploadSpy = jest.spyOn(uploadDocumentsService, 'uploadFile')
    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    const dragEvent = new Event('drop')
    dragEvent['dataTransfer'] = {
      items: [
        {
          kind: 'file',
          type: 'application/pdf',
          webkitGetAsEntry: () => ({
            isFile: true,
            isDirectory: false,
            file: (cb: (file: File) => void) => cb(file),
          }),
        },
      ],
      files: [],
    }
    component.onDrop(dragEvent as DragEvent)
    tick(3000)
    expect(toastSpy).toHaveBeenCalled()
    expect(uploadSpy).toHaveBeenCalled()
    discardPeriodicTasks()
  }))

  it('should show an error on traverseFileTree error', fakeAsync(() => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    const toastSpy = jest.spyOn(toastService, 'showError')
    const traverseSpy = jest
      .spyOn(component as any, 'traverseFileTree')
      .mockReturnValue(Promise.reject(new Error('Error traversing file tree')))
    fixture.detectChanges()

    // Simulate a drop with a directory entry
    const mockEntry = {
      isDirectory: true,
      isFile: false,
      createReader: () => ({ readEntries: jest.fn() }),
    } as unknown as FileSystemDirectoryEntry

    const event = {
      preventDefault: () => {},
      stopImmediatePropagation: () => {},
      dataTransfer: {
        items: [
          {
            kind: 'file',
            webkitGetAsEntry: () => mockEntry,
          },
        ],
      },
    } as unknown as DragEvent

    component.onDrop(event)

    tick() // flush microtasks (e.g., Promise.reject)

    expect(traverseSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith(
      $localize`Failed to read dropped items: Error traversing file tree`
    )

    discardPeriodicTasks()
  }))

  it('should support drag drop, initiate upload without DataTransfer API support', fakeAsync(() => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
    expect(component.fileIsOver).toBeFalsy()
    const overEvent = new Event('dragover') as DragEvent
    ;(overEvent as any).dataTransfer = { types: ['Files'] }
    component.onDragOver(overEvent)
    tick(1)
    fixture.detectChanges()
    expect(component.fileIsOver).toBeTruthy()
    component.onDragLeave(new Event('dragleave') as DragEvent)
    tick(700)
    fixture.detectChanges()
    // drop
    const toastSpy = jest.spyOn(toastService, 'show')
    const uploadSpy = jest.spyOn(uploadDocumentsService, 'uploadFile')
    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    const dragEvent = new Event('drop')
    dragEvent['dataTransfer'] = {
      items: [],
      files: [file],
    }
    component.onDrop(dragEvent as DragEvent)
    tick(3000)
    expect(toastSpy).toHaveBeenCalled()
    expect(uploadSpy).toHaveBeenCalled()
    discardPeriodicTasks()
  }))

  it('should resolve a single file when entry isFile', () => {
    const mockFile = new File(['data'], 'test.txt', { type: 'text/plain' })
    const mockEntry = {
      isFile: true,
      isDirectory: false,
      file: (cb: (f: File) => void) => cb(mockFile),
    } as unknown as FileSystemFileEntry

    return (component as any)
      .traverseFileTree(mockEntry)
      .then((result: File[]) => {
        expect(result).toEqual([mockFile])
      })
  })

  it('should resolve all files in a flat directory', async () => {
    const file1 = new File(['data'], 'file1.txt')
    const file2 = new File(['data'], 'file2.txt')

    const mockFileEntry1 = {
      isFile: true,
      isDirectory: false,
      file: (cb: (f: File) => void) => cb(file1),
    } as unknown as FileSystemFileEntry

    const mockFileEntry2 = {
      isFile: true,
      isDirectory: false,
      file: (cb: (f: File) => void) => cb(file2),
    } as unknown as FileSystemFileEntry

    let callCount = 0

    const mockDirEntry = {
      isFile: false,
      isDirectory: true,
      createReader: () => ({
        readEntries: (cb: (batch: FileSystemEntry[]) => void) => {
          if (callCount++ === 0) {
            cb([mockFileEntry1, mockFileEntry2])
          } else {
            cb([]) // second call: signal EOF
          }
        },
      }),
    } as unknown as FileSystemDirectoryEntry

    const result = await (component as any).traverseFileTree(mockDirEntry)
    expect(result).toEqual([file1, file2])
  })

  it('should resolve a non-file non-directory entry as an empty array', () => {
    const mockEntry = {
      isFile: false,
      isDirectory: false,
      file: (cb: (f: File) => void) => cb(new File([], '')),
    } as unknown as FileSystemEntry
    return (component as any)
      .traverseFileTree(mockEntry)
      .then((result: File[]) => {
        expect(result).toEqual([])
      })
  })

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
