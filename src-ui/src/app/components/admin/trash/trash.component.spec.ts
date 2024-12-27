import { ComponentFixture, TestBed } from '@angular/core/testing'

import { HttpClientTestingModule } from '@angular/common/http/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { By } from '@angular/platform-browser'
import { Router } from '@angular/router'
import {
  NgbModal,
  NgbPaginationModule,
  NgbPopoverModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, throwError } from 'rxjs'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { ToastService } from 'src/app/services/toast.service'
import { TrashService } from 'src/app/services/trash.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { TrashComponent } from './trash.component'

const documentsInTrash = [
  {
    id: 1,
    name: 'test1',
    created: new Date('2023-03-01T10:26:03.093116Z'),
    deleted_at: new Date('2023-03-01T10:26:03.093116Z'),
  },
  {
    id: 2,
    name: 'test2',
    created: new Date('2023-03-01T10:26:03.093116Z'),
    deleted_at: new Date('2023-03-01T10:26:03.093116Z'),
  },
]

describe('TrashComponent', () => {
  let component: TrashComponent
  let fixture: ComponentFixture<TrashComponent>
  let trashService: TrashService
  let modalService: NgbModal
  let toastService: ToastService
  let router: Router

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [
        TrashComponent,
        PageHeaderComponent,
        ConfirmDialogComponent,
        SafeHtmlPipe,
      ],
      imports: [
        HttpClientTestingModule,
        FormsModule,
        ReactiveFormsModule,
        NgbPopoverModule,
        NgbPaginationModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(TrashComponent)
    trashService = TestBed.inject(TrashService)
    modalService = TestBed.inject(NgbModal)
    toastService = TestBed.inject(ToastService)
    router = TestBed.inject(Router)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should call correct service method on reload', () => {
    jest.useFakeTimers()
    const trashSpy = jest.spyOn(trashService, 'getTrash')
    trashSpy.mockReturnValue(
      of({
        count: 2,
        all: documentsInTrash.map((d) => d.id),
        results: documentsInTrash,
      })
    )
    component.reload()
    jest.advanceTimersByTime(100)
    expect(trashSpy).toHaveBeenCalled()
    expect(component.documentsInTrash).toEqual(documentsInTrash)
  })

  it('should support delete document, show error if needed', () => {
    const trashSpy = jest.spyOn(trashService, 'emptyTrash')
    let modal
    modalService.activeInstances.subscribe((instances) => {
      modal = instances[0]
    })
    const toastErrorSpy = jest.spyOn(toastService, 'showError')

    // fail first
    trashSpy.mockReturnValue(throwError(() => 'Error'))
    component.delete(documentsInTrash[0])
    modal.componentInstance.confirmClicked.next()
    expect(toastErrorSpy).toHaveBeenCalled()

    trashSpy.mockReturnValue(of('OK'))
    component.delete(documentsInTrash[0])
    expect(modal).toBeDefined()
    modal.componentInstance.confirmClicked.next()
    expect(trashSpy).toHaveBeenCalled()
  })

  it('should support empty trash, show error if needed', () => {
    const trashSpy = jest.spyOn(trashService, 'emptyTrash')
    let modal
    modalService.activeInstances.subscribe((instances) => {
      modal = instances[instances.length - 1]
    })
    const toastErrorSpy = jest.spyOn(toastService, 'showError')

    // fail first
    trashSpy.mockReturnValue(throwError(() => 'Error'))
    component.emptyTrash()
    modal.componentInstance.confirmClicked.next()
    expect(toastErrorSpy).toHaveBeenCalled()

    trashSpy.mockReturnValue(of('OK'))
    component.emptyTrash()
    expect(modal).toBeDefined()
    modal.componentInstance.confirmClicked.next()
    expect(trashSpy).toHaveBeenCalled()
    modal.close()
    component.emptyTrash(new Set([1, 2]))
    modal.componentInstance.confirmClicked.next()
    expect(trashSpy).toHaveBeenCalledWith([1, 2])
  })

  it('should support restore document, show error if needed', () => {
    const restoreSpy = jest.spyOn(trashService, 'restoreDocuments')
    const reloadSpy = jest.spyOn(component, 'reload')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')

    // fail first
    restoreSpy.mockReturnValue(throwError(() => 'Error'))
    component.restore(documentsInTrash[0])
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    restoreSpy.mockReturnValue(of('OK'))
    component.restore(documentsInTrash[0])
    expect(restoreSpy).toHaveBeenCalledWith([documentsInTrash[0].id])
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should support restore all documents, show error if needed', () => {
    const restoreSpy = jest.spyOn(trashService, 'restoreDocuments')
    const reloadSpy = jest.spyOn(component, 'reload')
    const toastErrorSpy = jest.spyOn(toastService, 'showError')

    // fail first
    restoreSpy.mockReturnValue(throwError(() => 'Error'))
    component.restoreAll()
    expect(toastErrorSpy).toHaveBeenCalled()
    expect(reloadSpy).not.toHaveBeenCalled()

    restoreSpy.mockReturnValue(of('OK'))
    component.restoreAll()
    expect(restoreSpy).toHaveBeenCalled()
    expect(reloadSpy).toHaveBeenCalled()
    component.restoreAll(new Set([1, 2]))
    expect(restoreSpy).toHaveBeenCalledWith([1, 2])
  })

  it('should offer link to restored document', () => {
    let toasts
    const navigateSpy = jest.spyOn(router, 'navigate')
    toastService.getToasts().subscribe((allToasts) => {
      toasts = [...allToasts]
    })
    jest.spyOn(trashService, 'restoreDocuments').mockReturnValue(of('OK'))
    component.restore(documentsInTrash[0])
    expect(toasts.length).toEqual(1)
    toasts[0].action()
    expect(navigateSpy).toHaveBeenCalledWith([
      'documents',
      documentsInTrash[0].id,
    ])
  })

  it('should support toggle all items in view', () => {
    component.documentsInTrash = documentsInTrash
    expect(component.selectedDocuments.size).toEqual(0)
    const toggleAllSpy = jest.spyOn(component, 'toggleAll')
    const checkButton = fixture.debugElement.queryAll(
      By.css('input.form-check-input')
    )[0]
    checkButton.nativeElement.dispatchEvent(new Event('click'))
    checkButton.nativeElement.checked = true
    checkButton.nativeElement.dispatchEvent(new Event('click'))
    expect(toggleAllSpy).toHaveBeenCalled()
    expect(component.selectedDocuments.size).toEqual(documentsInTrash.length)
  })

  it('should support toggle item', () => {
    component.selectedDocuments = new Set([1])
    component.toggleSelected(documentsInTrash[0])
    expect(component.selectedDocuments.size).toEqual(0)
    component.toggleSelected(documentsInTrash[0])
    expect(component.selectedDocuments.size).toEqual(1)
  })

  it('should support clear selection', () => {
    component.selectedDocuments = new Set([1])
    component.clearSelection()
    expect(component.selectedDocuments.size).toEqual(0)
  })

  it('should correctly display days remaining', () => {
    expect(component.getDaysRemaining(documentsInTrash[0])).toBeLessThan(0)
    const tenDaysAgo = new Date()
    tenDaysAgo.setDate(tenDaysAgo.getDate() - 10)
    expect(
      component.getDaysRemaining({ deleted_at: tenDaysAgo })
    ).toBeGreaterThan(0) // 10 days ago but depends on month
  })
})
