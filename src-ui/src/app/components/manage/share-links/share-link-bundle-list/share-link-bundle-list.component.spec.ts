import { Clipboard } from '@angular/cdk/clipboard'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { FileVersion } from 'src/app/data/share-link'
import {
  ShareLinkBundleStatus,
  ShareLinkBundleSummary,
} from 'src/app/data/share-link-bundle'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { ShareLinkBundleService } from 'src/app/services/rest/share-link-bundle.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ShareLinkBundleListComponent } from './share-link-bundle-list.component'

class MockShareLinkBundleService {
  list = jest.fn()
  delete = jest.fn()
  rebuildBundle = jest.fn()
}

class MockToastService {
  showInfo = jest.fn()
  showError = jest.fn()
}

describe('ShareLinkBundleListComponent', () => {
  let component: ShareLinkBundleListComponent
  let fixture: ComponentFixture<ShareLinkBundleListComponent>
  let service: MockShareLinkBundleService
  let toastService: MockToastService
  let clipboard: Clipboard
  let originalApiBaseUrl: string

  beforeEach(() => {
    service = new MockShareLinkBundleService()
    toastService = new MockToastService()
    originalApiBaseUrl = environment.apiBaseUrl

    service.list.mockReturnValue(of({ count: 0, results: [] }))
    service.delete.mockReturnValue(of(true))
    service.rebuildBundle.mockReturnValue(of(sampleBundle()))

    TestBed.configureTestingModule({
      imports: [
        ShareLinkBundleListComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        { provide: ShareLinkBundleService, useValue: service },
        { provide: ToastService, useValue: toastService },
      ],
    })

    fixture = TestBed.createComponent(ShareLinkBundleListComponent)
    component = fixture.componentInstance
    clipboard = TestBed.inject(Clipboard)
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
    service.list.mockReset()
    service.list
      .mockReturnValueOnce(of({ count: bundles.length, results: bundles }))
      .mockReturnValue(of({ count: bundles.length, results: bundles }))

    fixture.detectChanges()

    expect(service.list).toHaveBeenCalledWith(1, 25, 'created', true)
    expect(component.bundles()).toEqual(bundles)
    expect(component.loading()).toBe(false)
    expect(component.error()).toBeNull()

    jest.advanceTimersByTime(5000)
    expect(service.list).toHaveBeenCalledTimes(2)
  })

  it('handles errors when loading bundles', () => {
    jest.useFakeTimers()
    service.list.mockReset()
    service.list
      .mockReturnValueOnce(throwError(() => new Error('load fail')))
      .mockReturnValue(of({ count: 0, results: [] }))

    fixture.detectChanges()

    expect(component.error()).toContain('Failed to load share link bundles.')
    expect(toastService.showError).toHaveBeenCalled()
    expect(component.loading()).toBe(false)

    jest.advanceTimersByTime(5000)
    expect(service.list).toHaveBeenCalledTimes(2)
  })

  it('loads another page', () => {
    fixture.detectChanges()

    component.setPage(2)

    expect(service.list).toHaveBeenLastCalledWith(2, 25, 'created', true)
  })

  it('sorts bundles and returns to the first page', () => {
    fixture.detectChanges()
    component.page.set(2)

    component.onSort({ column: 'status', reverse: false })

    expect(component.page()).toBe(1)
    expect(service.list).toHaveBeenLastCalledWith(1, 25, 'status', false)
  })

  it('marks expired share link bundles', () => {
    service.list.mockReturnValue(
      of({
        count: 1,
        results: [sampleBundle({ expiration: '2000-01-01T00:00:00.000Z' })],
      })
    )

    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain('Expired')
  })

  it('stores a changed page size and reloads from the first page', () => {
    fixture.detectChanges()
    const settingsService = TestBed.inject(SettingsService)
    jest
      .spyOn(settingsService, 'get')
      .mockReturnValueOnce({ share_link_bundles: 25 })
    const setSpy = jest.spyOn(settingsService, 'set')
    jest.spyOn(settingsService, 'storeSettings').mockReturnValue(of({}))
    component.page.set(2)

    component.pageSize = 100

    expect(setSpy).toHaveBeenCalledWith(SETTINGS_KEYS.OBJECT_LIST_SIZES, {
      share_link_bundles: 100,
    })
    expect(component.page()).toBe(1)
    expect(service.list).toHaveBeenLastCalledWith(1, 100, 'created', true)
  })

  it('copies bundle links when ready', () => {
    jest.useFakeTimers()
    jest.spyOn(clipboard, 'copy').mockReturnValue(true)
    fixture.detectChanges()

    const readyBundle = sampleBundle({
      slug: 'ready-slug',
      status: ShareLinkBundleStatus.Ready,
    })
    component.bundles.set([readyBundle])
    fixture.detectChanges()
    component.copy(readyBundle)

    expect(clipboard.copy).toHaveBeenCalledWith(
      component.getShareUrl(readyBundle)
    )
    expect(component.copiedSlug()).toBe('ready-slug')
    expect(toastService.showInfo).not.toHaveBeenCalled()
    fixture.detectChanges()
    expect(
      fixture.nativeElement.querySelector('.badge.show').textContent
    ).toContain('Copied!')

    jest.advanceTimersByTime(3000)
    expect(component.copiedSlug()).toBeNull()
    fixture.detectChanges()
    expect(fixture.nativeElement.querySelector('.badge.show')).toBeNull()
  })

  it('ignores copy requests for non-ready bundles', () => {
    const copySpy = jest.spyOn(clipboard, 'copy')
    fixture.detectChanges()
    component.copy(sampleBundle({ status: ShareLinkBundleStatus.Pending }))
    expect(copySpy).not.toHaveBeenCalled()
  })

  it('deletes bundles and refreshes list', () => {
    service.list.mockReturnValue(of({ count: 0, results: [] }))
    service.delete.mockReturnValue(of(true))

    fixture.detectChanges()

    component.delete(sampleBundle())

    expect(service.delete).toHaveBeenCalled()
    expect(toastService.showInfo).toHaveBeenCalledWith(
      expect.stringContaining('deleted.')
    )
    expect(service.list).toHaveBeenCalledTimes(2)
    expect(component.loading()).toBe(false)
  })

  it('handles delete errors gracefully', () => {
    service.list.mockReturnValue(of({ count: 0, results: [] }))
    service.delete.mockReturnValue(throwError(() => new Error('delete fail')))

    fixture.detectChanges()

    component.delete(sampleBundle())

    expect(toastService.showError).toHaveBeenCalled()
    expect(component.loading()).toBe(false)
  })

  it('retries bundle build and replaces existing entry', () => {
    service.list.mockReturnValue(of({ count: 0, results: [] }))
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
    service.list.mockReturnValue(of({ count: 0, results: [] }))
    service.rebuildBundle.mockReturnValue(
      of(sampleBundle({ id: 99, slug: 'new-slug' }))
    )

    fixture.detectChanges()

    component.bundles.set([sampleBundle()])
    component.retry({ id: 99 } as ShareLinkBundleSummary)

    expect(component.bundles().find((bundle) => bundle.id === 99)).toBeTruthy()
  })

  it('handles retry errors', () => {
    service.list.mockReturnValue(of({ count: 0, results: [] }))
    service.rebuildBundle.mockReturnValue(throwError(() => new Error('fail')))

    fixture.detectChanges()

    component.retry(sampleBundle())

    expect(toastService.showError).toHaveBeenCalled()
  })

  it('maps status and file version helpers', () => {
    service.list.mockReturnValue(of({ count: 0, results: [] }))
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
  })
})
