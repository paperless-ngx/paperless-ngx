import { Clipboard } from '@angular/cdk/clipboard'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { RouterTestingModule } from '@angular/router/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { FileVersion, ShareLink } from 'src/app/data/share-link'
import { ShareLinkService } from 'src/app/services/rest/share-link.service'
import { ToastService } from 'src/app/services/toast.service'
import { ShareLinkListComponent } from './share-link-list.component'

describe('ShareLinkListComponent', () => {
  let component: ShareLinkListComponent
  let fixture: ComponentFixture<ShareLinkListComponent>
  let service: jest.Mocked<Pick<ShareLinkService, 'list' | 'delete'>>
  let clipboard: Clipboard
  let toastService: jest.Mocked<Pick<ToastService, 'showInfo' | 'showError'>>

  const link = {
    id: 1,
    document: 42,
    slug: 'share-slug',
    created: new Date().toISOString(),
    expiration: null,
    file_version: FileVersion.Archive,
  } as ShareLink

  beforeEach(() => {
    service = {
      list: jest.fn().mockReturnValue(of({ count: 1, results: [link] })),
      delete: jest.fn().mockReturnValue(of(true)),
    }
    toastService = {
      showInfo: jest.fn(),
      showError: jest.fn(),
    }

    TestBed.configureTestingModule({
      imports: [
        ShareLinkListComponent,
        NgxBootstrapIconsModule.pick(allIcons),
        RouterTestingModule,
      ],
      providers: [
        { provide: ShareLinkService, useValue: service },
        { provide: ToastService, useValue: toastService },
      ],
    })

    fixture = TestBed.createComponent(ShareLinkListComponent)
    component = fixture.componentInstance
    clipboard = TestBed.inject(Clipboard)
  })

  afterEach(() => {
    jest.clearAllTimers()
    jest.useRealTimers()
  })

  it('loads and renders document share links', () => {
    fixture.detectChanges()

    expect(service.list).toHaveBeenCalledWith(1, 25, 'created', true)
    expect(component.links()).toEqual([link])
    expect(fixture.nativeElement.textContent).toContain('Document #42')
  })

  it('loads another page', () => {
    fixture.detectChanges()
    component.setPage(2)

    expect(service.list).toHaveBeenLastCalledWith(2, 25, 'created', true)
  })

  it('shows local copy feedback without a toast', () => {
    jest.useFakeTimers()
    jest.spyOn(clipboard, 'copy').mockReturnValue(true)
    fixture.detectChanges()

    component.copy(link)
    fixture.detectChanges()

    expect(component.copiedID()).toBe(link.id)
    expect(fixture.nativeElement.querySelector('.badge.show')).not.toBeNull()
    expect(toastService.showInfo).not.toHaveBeenCalled()

    jest.advanceTimersByTime(3000)
    expect(component.copiedID()).toBeNull()
  })

  it('deletes a link and reloads the list', () => {
    fixture.detectChanges()
    component.delete(link)

    expect(service.delete).toHaveBeenCalledWith(link)
    expect(service.list).toHaveBeenCalledTimes(2)
    expect(toastService.showInfo).toHaveBeenCalled()
  })

  it('shows an error when loading fails', () => {
    service.list.mockReturnValue(throwError(() => new Error('load failed')))
    fixture.detectChanges()

    expect(component.error()).toContain('Failed to load share links.')
    expect(toastService.showError).toHaveBeenCalled()
  })
})
