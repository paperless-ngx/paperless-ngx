import { Clipboard } from '@angular/cdk/clipboard'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { FileVersion } from 'src/app/data/share-link'
import {
  ShareLinkBundleStatus,
  ShareLinkBundleSummary,
} from 'src/app/data/share-link-bundle'
import { ShareLinkBundleService } from 'src/app/services/rest/share-link-bundle.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ShareLinkBundleManageDialogComponent } from './share-link-bundle-manage-dialog.component'

class MockShareLinkBundleService {
  listAllBundles = jest.fn()
  delete = jest.fn()
  rebuildBundle = jest.fn()
}

class MockToastService {
  showInfo = jest.fn()
  showError = jest.fn()
}

describe('ShareLinkBundleManageDialogComponent', () => {
  let component: ShareLinkBundleManageDialogComponent
  let fixture: ComponentFixture<ShareLinkBundleManageDialogComponent>
  let service: MockShareLinkBundleService
  let toastService: MockToastService
  let clipboard: Clipboard
  let activeModal: NgbActiveModal
  let originalApiBaseUrl: string

  beforeEach(() => {
    service = new MockShareLinkBundleService()
    toastService = new MockToastService()
    originalApiBaseUrl = environment.apiBaseUrl

    service.listAllBundles.mockReturnValue(of([]))
    service.delete.mockReturnValue(of(true))
    service.rebuildBundle.mockReturnValue(of(sampleBundle()))

    TestBed.configureTestingModule({
      imports: [
        ShareLinkBundleManageDialogComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        NgbActiveModal,
        { provide: ShareLinkBundleService, useValue: service },
        { provide: ToastService, useValue: toastService },
      ],
    })

    fixture = TestBed.createComponent(ShareLinkBundleManageDialogComponent)
    component = fixture.componentInstance
    clipboard = TestBed.inject(Clipboard)
    activeModal = TestBed.inject(NgbActiveModal)
  })

  afterEach(() => {
    component.ngOnDestroy()
    fixture.destroy()
    environment.apiBaseUrl = originalApiBaseUrl
    jest.clearAllMocks()
    jest.useRealTimers()
  })

  const sampleBundle = (overrides: Partial<ShareLinkBundleSummary> = {}) =>
    ({
      id: 1,
      slug: 'bundle-slug',
      created: new Date().toISOString(),
      document_count: 1,
      documents: [1],
      status: ShareLinkBundleStatus.Pending,
      file_version: FileVersion.Archive,
      last_error: undefined,
      ...overrides,
    }) as ShareLinkBundleSummary

  it('loads bundles on init and polls periodically', () => {
    jest.useFakeTimers()
    const bundles = [sampleBundle({ status: ShareLinkBundleStatus.Ready })]
    service.listAllBundles.mockReset()
    service.listAllBundles
      .mockReturnValueOnce(of(bundles))
      .mockReturnValue(of(bundles))

    fixture.detectChanges()

    expect(service.listAllBundles).toHaveBeenCalledTimes(1)
    expect(component.bundles()).toEqual(bundles)
    expect(component.loading()).toBe(false)
    expect(component.error()).toBeNull()

    jest.advanceTimersByTime(5000)
    expect(service.listAllBundles).toHaveBeenCalledTimes(2)
  })

  it('handles errors when loading bundles', () => {
    jest.useFakeTimers()
    service.listAllBundles.mockReset()
    service.listAllBundles
      .mockReturnValueOnce(throwError(() => new Error('load fail')))
      .mockReturnValue(of([]))

    fixture.detectChanges()

    expect(component.error()).toContain('Failed to load share link bundles.')
    expect(toastService.showError).toHaveBeenCalled()
    expect(component.loading()).toBe(false)

    jest.advanceTimersByTime(5000)
    expect(service.listAllBundles).toHaveBeenCalledTimes(2)
  })

  it('copies bundle links when ready', () => {
    jest.useFakeTimers()
    jest.spyOn(clipboard, 'copy').mockReturnValue(true)
    fixture.detectChanges()

    const readyBundle = sampleBundle({
      slug: 'ready-slug',
      status: ShareLinkBundleStatus.Ready,
    })
    component.copy(readyBundle)

    expect(clipboard.copy).toHaveBeenCalledWith(
      component.getShareUrl(readyBundle)
    )
    expect(component.copiedSlug()).toBe('ready-slug')
    expect(toastService.showInfo).toHaveBeenCalled()

    jest.advanceTimersByTime(3000)
    expect(component.copiedSlug()).toBeNull()
  })

  it('ignores copy requests for non-ready bundles', () => {
    const copySpy = jest.spyOn(clipboard, 'copy')
    fixture.detectChanges()
    component.copy(sampleBundle({ status: ShareLinkBundleStatus.Pending }))
    expect(copySpy).not.toHaveBeenCalled()
  })

  it('deletes bundles and refreshes list', () => {
    service.listAllBundles.mockReturnValue(of([]))
    service.delete.mockReturnValue(of(true))

    fixture.detectChanges()

    component.delete(sampleBundle())

    expect(service.delete).toHaveBeenCalled()
    expect(toastService.showInfo).toHaveBeenCalledWith(
      expect.stringContaining('deleted.')
    )
    expect(service.listAllBundles).toHaveBeenCalledTimes(2)
    expect(component.loading()).toBe(false)
  })

  it('handles delete errors gracefully', () => {
    service.listAllBundles.mockReturnValue(of([]))
    service.delete.mockReturnValue(throwError(() => new Error('delete fail')))

    fixture.detectChanges()

    component.delete(sampleBundle())

    expect(toastService.showError).toHaveBeenCalled()
    expect(component.loading()).toBe(false)
  })

  it('retries bundle build and replaces existing entry', () => {
    service.listAllBundles.mockReturnValue(of([]))
    const updated = sampleBundle({ status: ShareLinkBundleStatus.Ready })
    service.rebuildBundle.mockReturnValue(of(updated))

    fixture.detectChanges()

    component.bundles.set([sampleBundle()])
    component.retry(component.bundles()[0])

    expect(service.rebuildBundle).toHaveBeenCalledWith(updated.id)
    expect(component.bundles()[0].status).toBe(ShareLinkBundleStatus.Ready)
    expect(toastService.showInfo).toHaveBeenCalled()
  })

  it('adds new bundle when retry returns unknown entry', () => {
    service.listAllBundles.mockReturnValue(of([]))
    service.rebuildBundle.mockReturnValue(
      of(sampleBundle({ id: 99, slug: 'new-slug' }))
    )

    fixture.detectChanges()

    component.bundles.set([sampleBundle()])
    component.retry({ id: 99 } as ShareLinkBundleSummary)

    expect(component.bundles().find((bundle) => bundle.id === 99)).toBeTruthy()
  })

  it('handles retry errors', () => {
    service.listAllBundles.mockReturnValue(of([]))
    service.rebuildBundle.mockReturnValue(throwError(() => new Error('fail')))

    fixture.detectChanges()

    component.retry(sampleBundle())

    expect(toastService.showError).toHaveBeenCalled()
  })

  it('maps helpers and closes dialog', () => {
    service.listAllBundles.mockReturnValue(of([]))
    fixture.detectChanges()

    expect(component.statusLabel(ShareLinkBundleStatus.Processing)).toContain(
      'Processing'
    )
    expect(component.fileVersionLabel(FileVersion.Original)).toContain(
      'Original'
    )

    environment.apiBaseUrl = 'https://example.com/api/'
    const url = component.getShareUrl(sampleBundle({ slug: 'sluggy' }))
    expect(url).toBe('https://example.com/share/sluggy')

    const closeSpy = jest.spyOn(activeModal, 'close')
    component.close()
    expect(closeSpy).toHaveBeenCalled()
  })
})
