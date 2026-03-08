import { DatePipe } from '@angular/common'
import { SimpleChange } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { Subject, of, throwError } from 'rxjs'
import { DocumentVersionInfo } from 'src/app/data/document'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import {
  UploadState,
  WebsocketStatusService,
} from 'src/app/services/websocket-status.service'
import { DocumentVersionDropdownComponent } from './document-version-dropdown.component'

describe('DocumentVersionDropdownComponent', () => {
  let component: DocumentVersionDropdownComponent
  let fixture: ComponentFixture<DocumentVersionDropdownComponent>
  let documentService: jest.Mocked<
    Pick<
      DocumentService,
      'deleteVersion' | 'getVersions' | 'uploadVersion' | 'updateVersionLabel'
    >
  >
  let toastService: jest.Mocked<Pick<ToastService, 'showError' | 'showInfo'>>
  let finished$: Subject<{ taskId: string }>
  let failed$: Subject<{ taskId: string; message?: string }>

  beforeEach(async () => {
    finished$ = new Subject<{ taskId: string }>()
    failed$ = new Subject<{ taskId: string; message?: string }>()
    documentService = {
      deleteVersion: jest.fn(),
      getVersions: jest.fn(),
      uploadVersion: jest.fn(),
      updateVersionLabel: jest.fn(),
    }
    toastService = {
      showError: jest.fn(),
      showInfo: jest.fn(),
    }

    await TestBed.configureTestingModule({
      imports: [
        DocumentVersionDropdownComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        DatePipe,
        {
          provide: DocumentService,
          useValue: documentService,
        },
        {
          provide: SettingsService,
          useValue: {
            get: () => null,
          },
        },
        {
          provide: ToastService,
          useValue: toastService,
        },
        {
          provide: WebsocketStatusService,
          useValue: {
            onDocumentConsumptionFinished: () => finished$,
            onDocumentConsumptionFailed: () => failed$,
          },
        },
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(DocumentVersionDropdownComponent)
    component = fixture.componentInstance
    component.documentId = 3
    component.selectedVersionId = 3
    component.versions = [
      {
        id: 3,
        is_root: true,
        checksum: 'aaaa',
      },
      {
        id: 10,
        is_root: false,
        checksum: 'bbbb',
      },
    ]
    fixture.detectChanges()
  })

  it('selectVersion should emit the selected id', () => {
    const emitSpy = jest.spyOn(component.versionSelected, 'emit')
    component.selectVersion(10)
    expect(emitSpy).toHaveBeenCalledWith(10)
  })

  it('deleteVersion should refresh versions and select fallback when deleting current selection', () => {
    const updatedVersions: DocumentVersionInfo[] = [
      { id: 3, is_root: true, checksum: 'aaaa' },
      { id: 20, is_root: false, checksum: 'cccc' },
    ]
    component.selectedVersionId = 10
    documentService.deleteVersion.mockReturnValue(
      of({ result: 'deleted', current_version_id: 3 })
    )
    documentService.getVersions.mockReturnValue(
      of({ id: 3, versions: updatedVersions } as any)
    )
    const versionsEmitSpy = jest.spyOn(component.versionsUpdated, 'emit')
    const selectedEmitSpy = jest.spyOn(component.versionSelected, 'emit')

    component.deleteVersion(10)

    expect(documentService.deleteVersion).toHaveBeenCalledWith(3, 10)
    expect(documentService.getVersions).toHaveBeenCalledWith(3)
    expect(versionsEmitSpy).toHaveBeenCalledWith(updatedVersions)
    expect(selectedEmitSpy).toHaveBeenCalledWith(3)
  })

  it('deleteVersion should show an error toast on failure', () => {
    const error = new Error('delete failed')
    documentService.deleteVersion.mockReturnValue(throwError(() => error))

    component.deleteVersion(10)

    expect(toastService.showError).toHaveBeenCalledWith(
      'Error deleting version',
      error
    )
  })

  it('beginEditingVersion should set active row and draft label', () => {
    component.userCanEdit = true
    component.userIsOwner = true
    const version = {
      id: 10,
      is_root: false,
      checksum: 'bbbb',
      version_label: 'Current',
    } as DocumentVersionInfo

    component.beginEditingVersion(version)

    expect(component.editingVersionId).toEqual(10)
    expect(component.versionLabelDraft).toEqual('Current')
  })

  it('submitEditedVersionLabel should close editor without save if unchanged', () => {
    const version = {
      id: 10,
      is_root: false,
      checksum: 'bbbb',
      version_label: 'Current',
    } as DocumentVersionInfo
    const saveSpy = jest.spyOn(component, 'saveVersionLabel')
    component.editingVersionId = 10
    component.versionLabelDraft = '  Current  '

    component.submitEditedVersionLabel(version)

    expect(saveSpy).not.toHaveBeenCalled()
    expect(component.editingVersionId).toBeNull()
    expect(component.versionLabelDraft).toEqual('')
  })

  it('submitEditedVersionLabel should call saveVersionLabel when changed', () => {
    const version = {
      id: 10,
      is_root: false,
      checksum: 'bbbb',
      version_label: 'Current',
    } as DocumentVersionInfo
    const saveSpy = jest
      .spyOn(component, 'saveVersionLabel')
      .mockImplementation(() => {})
    component.editingVersionId = 10
    component.versionLabelDraft = '  Updated  '

    component.submitEditedVersionLabel(version)

    expect(saveSpy).toHaveBeenCalledWith(10, 'Updated')
    expect(component.editingVersionId).toBeNull()
  })

  it('saveVersionLabel should update the version and emit versionsUpdated', () => {
    documentService.updateVersionLabel.mockReturnValue(
      of({
        id: 10,
        version_label: 'Updated',
        is_root: false,
      } as any)
    )
    const emitSpy = jest.spyOn(component.versionsUpdated, 'emit')

    component.saveVersionLabel(10, 'Updated')

    expect(documentService.updateVersionLabel).toHaveBeenCalledWith(
      3,
      10,
      'Updated'
    )
    expect(emitSpy).toHaveBeenCalledWith([
      { id: 3, is_root: true, checksum: 'aaaa' },
      { id: 10, is_root: false, checksum: 'bbbb', version_label: 'Updated' },
    ])
    expect(component.savingVersionLabelId).toBeNull()
  })

  it('saveVersionLabel should show error toast on failure', () => {
    const error = new Error('save failed')
    documentService.updateVersionLabel.mockReturnValue(throwError(() => error))

    component.saveVersionLabel(10, 'Updated')

    expect(toastService.showError).toHaveBeenCalledWith(
      'Error updating version label',
      error
    )
    expect(component.savingVersionLabelId).toBeNull()
  })

  it('onVersionFileSelected should upload and update versions after websocket success', () => {
    const versions: DocumentVersionInfo[] = [
      { id: 3, is_root: true, checksum: 'aaaa' },
      { id: 20, is_root: false, checksum: 'cccc' },
    ]
    const file = new File(['test'], 'new-version.pdf', {
      type: 'application/pdf',
    })
    const input = document.createElement('input')
    Object.defineProperty(input, 'files', { value: [file] })
    component.newVersionLabel = '  Updated scan  '
    documentService.uploadVersion.mockReturnValue(
      of({ task_id: 'task-1' } as any)
    )
    documentService.getVersions.mockReturnValue(of({ id: 3, versions } as any))
    const versionsEmitSpy = jest.spyOn(component.versionsUpdated, 'emit')
    const selectedEmitSpy = jest.spyOn(component.versionSelected, 'emit')

    component.onVersionFileSelected({ target: input } as Event)
    finished$.next({ taskId: 'task-1' })

    expect(documentService.uploadVersion).toHaveBeenCalledWith(
      3,
      file,
      'Updated scan'
    )
    expect(toastService.showInfo).toHaveBeenCalled()
    expect(documentService.getVersions).toHaveBeenCalledWith(3)
    expect(versionsEmitSpy).toHaveBeenCalledWith(versions)
    expect(selectedEmitSpy).toHaveBeenCalledWith(20)
    expect(component.newVersionLabel).toEqual('')
    expect(component.versionUploadState).toEqual(UploadState.Idle)
    expect(component.versionUploadError).toBeNull()
  })

  it('onVersionFileSelected should set failed state after websocket failure', () => {
    const file = new File(['test'], 'new-version.pdf', {
      type: 'application/pdf',
    })
    const input = document.createElement('input')
    Object.defineProperty(input, 'files', { value: [file] })
    documentService.uploadVersion.mockReturnValue(of('task-1'))

    component.onVersionFileSelected({ target: input } as Event)
    failed$.next({ taskId: 'task-1', message: 'processing failed' })

    expect(component.versionUploadState).toEqual(UploadState.Failed)
    expect(component.versionUploadError).toEqual('processing failed')
    expect(documentService.getVersions).not.toHaveBeenCalled()
  })

  it('onVersionFileSelected should fail when backend response has no task id', () => {
    const file = new File(['test'], 'new-version.pdf', {
      type: 'application/pdf',
    })
    const input = document.createElement('input')
    Object.defineProperty(input, 'files', { value: [file] })
    documentService.uploadVersion.mockReturnValue(of({} as any))

    component.onVersionFileSelected({ target: input } as Event)

    expect(component.versionUploadState).toEqual(UploadState.Failed)
    expect(component.versionUploadError).toEqual('Missing task ID.')
    expect(documentService.getVersions).not.toHaveBeenCalled()
  })

  it('onVersionFileSelected should show error when upload request fails', () => {
    const file = new File(['test'], 'new-version.pdf', {
      type: 'application/pdf',
    })
    const input = document.createElement('input')
    Object.defineProperty(input, 'files', { value: [file] })
    const error = new Error('upload failed')
    documentService.uploadVersion.mockReturnValue(throwError(() => error))

    component.onVersionFileSelected({ target: input } as Event)

    expect(component.versionUploadState).toEqual(UploadState.Failed)
    expect(component.versionUploadError).toEqual('upload failed')
    expect(toastService.showError).toHaveBeenCalledWith(
      'Error uploading new version',
      error
    )
  })

  it('ngOnChanges should clear upload status on document switch', () => {
    component.versionUploadState = UploadState.Failed
    component.versionUploadError = 'something failed'
    component.editingVersionId = 10
    component.versionLabelDraft = 'draft'

    component.ngOnChanges({
      documentId: new SimpleChange(3, 4, false),
    })

    expect(component.versionUploadState).toEqual(UploadState.Idle)
    expect(component.versionUploadError).toBeNull()
    expect(component.editingVersionId).toBeNull()
    expect(component.versionLabelDraft).toEqual('')
  })
})
