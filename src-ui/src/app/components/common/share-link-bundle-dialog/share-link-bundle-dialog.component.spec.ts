import { Clipboard } from '@angular/cdk/clipboard'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { FileVersion } from 'src/app/data/share-link'
import {
  ShareLinkBundleStatus,
  ShareLinkBundleSummary,
} from 'src/app/data/share-link-bundle'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ShareLinkBundleDialogComponent } from './share-link-bundle-dialog.component'

class MockToastService {
  showInfo = jest.fn()
  showError = jest.fn()
}

describe('ShareLinkBundleDialogComponent', () => {
  let component: ShareLinkBundleDialogComponent
  let fixture: ComponentFixture<ShareLinkBundleDialogComponent>
  let clipboard: Clipboard
  let toastService: MockToastService
  let activeModal: NgbActiveModal
  let originalApiBaseUrl: string

  beforeEach(() => {
    originalApiBaseUrl = environment.apiBaseUrl
    toastService = new MockToastService()

    TestBed.configureTestingModule({
      imports: [
        ShareLinkBundleDialogComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        NgbActiveModal,
        { provide: ToastService, useValue: toastService },
      ],
    })

    fixture = TestBed.createComponent(ShareLinkBundleDialogComponent)
    component = fixture.componentInstance
    clipboard = TestBed.inject(Clipboard)
    activeModal = TestBed.inject(NgbActiveModal)
    fixture.detectChanges()
  })

  afterEach(() => {
    jest.clearAllTimers()
    environment.apiBaseUrl = originalApiBaseUrl
  })

  it('builds payload and emits confirm on submit', () => {
    const confirmSpy = jest.spyOn(component.confirmClicked, 'emit')
    component.documents = [
      { id: 1, title: 'Doc 1' } as any,
      { id: 2, title: 'Doc 2' } as any,
    ]
    component.form.setValue({
      shareArchiveVersion: false,
      expirationDays: 3,
    })

    component.submit()

    expect(component.payload).toEqual({
      document_ids: [1, 2],
      file_version: FileVersion.Original,
      expiration_days: 3,
    })
    expect(component.buttonsEnabled).toBe(false)
    expect(confirmSpy).toHaveBeenCalled()

    component.form.setValue({
      shareArchiveVersion: true,
      expirationDays: 7,
    })
    component.submit()

    expect(component.payload).toEqual({
      document_ids: [1, 2],
      file_version: FileVersion.Archive,
      expiration_days: 7,
    })
  })

  it('ignores submit when bundle already created', () => {
    component.createdBundle = { id: 1 } as ShareLinkBundleSummary
    const confirmSpy = jest.spyOn(component, 'confirm')
    component.submit()
    expect(confirmSpy).not.toHaveBeenCalled()
  })

  it('limits preview to ten documents', () => {
    const docs = Array.from({ length: 12 }).map((_, index) => ({
      id: index + 1,
    }))
    component.documents = docs as any

    expect(component.selectionCount).toBe(12)
    expect(component.documentPreview).toHaveLength(10)
    expect(component.documentPreview[0].id).toBe(1)
  })

  it('copies share link and resets state after timeout', fakeAsync(() => {
    const copySpy = jest.spyOn(clipboard, 'copy').mockReturnValue(true)
    const bundle = {
      slug: 'bundle-slug',
      status: ShareLinkBundleStatus.Ready,
    } as ShareLinkBundleSummary

    component.copy(bundle)

    expect(copySpy).toHaveBeenCalledWith(component.getShareUrl(bundle))
    expect(component.copied).toBe(true)
    expect(toastService.showInfo).toHaveBeenCalled()

    tick(3000)
    expect(component.copied).toBe(false)
  }))

  it('generates share URLs based on API base URL', () => {
    environment.apiBaseUrl = 'https://example.com/api/'
    expect(
      component.getShareUrl({ slug: 'abc' } as ShareLinkBundleSummary)
    ).toBe('https://example.com/share/abc')
  })

  it('opens manage dialog when callback provided', () => {
    const manageSpy = jest.fn()
    component.onOpenManage = manageSpy
    component.openManage()
    expect(manageSpy).toHaveBeenCalled()
  })

  it('falls back to cancel when manage callback missing', () => {
    const cancelSpy = jest.spyOn(component, 'cancel')
    component.onOpenManage = undefined
    component.openManage()
    expect(cancelSpy).toHaveBeenCalled()
  })

  it('maps status and file version labels', () => {
    expect(component.statusLabel(ShareLinkBundleStatus.Processing)).toContain(
      'Processing'
    )
    expect(component.fileVersionLabel(FileVersion.Archive)).toContain('Archive')
  })

  it('closes dialog when cancel invoked', () => {
    const closeSpy = jest.spyOn(activeModal, 'close')
    component.cancel()
    expect(closeSpy).toHaveBeenCalled()
  })
})
