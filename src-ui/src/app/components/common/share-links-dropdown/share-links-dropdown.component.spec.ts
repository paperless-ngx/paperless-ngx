import {
  HttpTestingController,
  HttpClientTestingModule,
} from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { of, throwError } from 'rxjs'
import {
  PaperlessFileVersion,
  PaperlessShareLink,
} from 'src/app/data/paperless-share-link'
import { ShareLinkService } from 'src/app/services/rest/share-link.service'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ShareLinksDropdownComponent } from './share-links-dropdown.component'
import { Clipboard } from '@angular/cdk/clipboard'

describe('ShareLinksDropdownComponent', () => {
  let component: ShareLinksDropdownComponent
  let fixture: ComponentFixture<ShareLinksDropdownComponent>
  let shareLinkService: ShareLinkService
  let toastService: ToastService
  let httpController: HttpTestingController
  let clipboard: Clipboard

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [ShareLinksDropdownComponent],
      imports: [HttpClientTestingModule, FormsModule, ReactiveFormsModule],
    })

    fixture = TestBed.createComponent(ShareLinksDropdownComponent)
    shareLinkService = TestBed.inject(ShareLinkService)
    toastService = TestBed.inject(ToastService)
    httpController = TestBed.inject(HttpTestingController)
    clipboard = TestBed.inject(Clipboard)

    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should support refresh to retrieve links', () => {
    const getSpy = jest.spyOn(shareLinkService, 'getLinksForDocument')
    component.documentId = 99

    const now = new Date()
    const expiration7days = new Date()
    expiration7days.setDate(now.getDate() + 7)

    getSpy.mockReturnValue(
      of([
        {
          id: 1,
          slug: '1234slug',
          created: now.toISOString(),
          document: 99,
          file_version: PaperlessFileVersion.Archive,
          expiration: expiration7days.toISOString(),
        },
        {
          id: 1,
          slug: '1234slug',
          created: now.toISOString(),
          document: 99,
          file_version: PaperlessFileVersion.Original,
          expiration: null,
        },
      ])
    )

    component.refresh()
    expect(getSpy).toHaveBeenCalled()

    fixture.detectChanges()

    expect(component.shareLinks).toHaveLength(2)
  })

  it('should show error on refresh if needed', () => {
    const toastSpy = jest.spyOn(toastService, 'showError')
    jest
      .spyOn(shareLinkService, 'getLinksForDocument')
      .mockReturnValueOnce(throwError(() => new Error('Unable to get links')))
    component.documentId = 99

    component.refresh()
    fixture.detectChanges()
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should support link creation then refresh & copy url', fakeAsync(() => {
    const createSpy = jest.spyOn(shareLinkService, 'createLinkForDocument')
    component.documentId = 99
    component.expirationDays = 7
    component.archiveVersion = false

    const expiration = new Date()
    expiration.setDate(expiration.getDate() + 7)

    const copySpy = jest.spyOn(clipboard, 'copy')
    const refreshSpy = jest.spyOn(component, 'refresh')

    component.createLink()
    expect(createSpy).toHaveBeenCalledWith(99, 'original', expiration)

    httpController.expectOne(`${environment.apiBaseUrl}share_links/`).flush({
      id: 1,
      slug: '1234slug',
      document: 99,
      expiration: expiration.toISOString(),
    })
    fixture.detectChanges()
    tick(3000)

    expect(copySpy).toHaveBeenCalled()
    expect(refreshSpy).toHaveBeenCalled()
  }))

  it('should show error on link creation if needed', () => {
    component.documentId = 99
    component.expirationDays = 7

    const expiration = new Date()
    expiration.setDate(expiration.getDate() + 7)

    const toastSpy = jest.spyOn(toastService, 'showError')

    component.createLink()

    httpController
      .expectOne(`${environment.apiBaseUrl}share_links/`)
      .flush(
        { error: 'Share link error' },
        { status: 500, statusText: 'error' }
      )
    fixture.detectChanges()

    expect(toastSpy).toHaveBeenCalled()
  })

  it('should support delete links & refresh', () => {
    const deleteSpy = jest.spyOn(shareLinkService, 'delete')
    deleteSpy.mockReturnValue(of(true))
    const refreshSpy = jest.spyOn(component, 'refresh')

    component.delete({ id: 12 } as PaperlessShareLink)
    fixture.detectChanges()
    expect(deleteSpy).toHaveBeenCalledWith({ id: 12 })
    expect(refreshSpy).toHaveBeenCalled()
  })

  it('should show error on delete if needed', () => {
    const toastSpy = jest.spyOn(toastService, 'showError')
    jest
      .spyOn(shareLinkService, 'delete')
      .mockReturnValueOnce(throwError(() => new Error('Unable to delete link')))
    component.delete(null)
    fixture.detectChanges()
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should format days remaining', () => {
    const now = new Date()
    const expiration7days = new Date()
    expiration7days.setDate(now.getDate() + 7)
    const expiration1day = new Date()
    expiration1day.setDate(now.getDate() + 1)

    expect(
      component.getDaysRemaining({
        expiration: expiration7days.toISOString(),
      } as PaperlessShareLink)
    ).toEqual('7 days')
    expect(
      component.getDaysRemaining({
        expiration: expiration1day.toISOString(),
      } as PaperlessShareLink)
    ).toEqual('1 day')
  })

  // coverage
  it('should support share', () => {
    const link = { slug: '12345slug' } as PaperlessShareLink
    if (!('share' in navigator))
      Object.defineProperty(navigator, 'share', { value: (obj: any) => {} })
    // const navigatorSpy = jest.spyOn(navigator, 'share')
    component.share(link)
    // expect(navigatorSpy).toHaveBeenCalledWith({ url: component.getShareUrl(link) })
  })
})
