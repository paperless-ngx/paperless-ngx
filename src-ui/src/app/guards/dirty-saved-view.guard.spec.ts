import { TestBed } from '@angular/core/testing'
import { DirtySavedViewGuard } from './dirty-saved-view.guard'
import { NgbModal, NgbModalRef } from '@ng-bootstrap/ng-bootstrap'
import { SettingsService } from '../services/settings.service'
import { DocumentListComponent } from '../components/document-list/document-list.component'
import { RouterTestingModule } from '@angular/router/testing'
import { routes } from '../app-routing.module'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ConfirmDialogComponent } from '../components/common/confirm-dialog/confirm-dialog.component'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

describe('DirtySavedViewGuard', () => {
  let guard: DirtySavedViewGuard
  let settingsService: SettingsService
  let modalService: NgbModal
  let component: DocumentListComponent

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [ConfirmDialogComponent],
      imports: [RouterTestingModule.withRoutes(routes)],
      providers: [
        DirtySavedViewGuard,
        SettingsService,
        NgbModal,
        DocumentListComponent,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    settingsService = TestBed.inject(SettingsService)
    modalService = TestBed.inject(NgbModal)
    guard = TestBed.inject(DirtySavedViewGuard)
    const fixture = TestBed.createComponent(DocumentListComponent)
    component = fixture.componentInstance
  })

  it('should deactivate if component is not dirty', () => {
    jest
      .spyOn(DocumentListComponent.prototype, 'savedViewIsModified', 'get')
      .mockImplementation(() => {
        return false
      })
    const canDeactivate = guard.canDeactivate(component)

    expect(canDeactivate).toBeTruthy()
  })

  it('should not warn on deactivate if component is dirty & setting disabled', () => {
    jest
      .spyOn(DocumentListComponent.prototype, 'savedViewIsModified', 'get')
      .mockImplementation(() => {
        return true
      })

    jest.spyOn(settingsService, 'get').mockImplementation(() => {
      return false
    })

    const modalSpy = jest.spyOn(modalService, 'open')

    const canDeactivate = guard.canDeactivate(component)

    expect(canDeactivate).toBeTruthy()
    expect(modalSpy).not.toHaveBeenCalled()

    const saveSpy = jest.spyOn(component, 'saveViewConfig')
    expect(saveSpy).not.toHaveBeenCalled()
  })

  it('should warn on deactivate if component is dirty & setting enabled', () => {
    jest
      .spyOn(DocumentListComponent.prototype, 'savedViewIsModified', 'get')
      .mockImplementation(() => {
        return true
      })

    jest.spyOn(settingsService, 'get').mockImplementation(() => {
      return true
    })

    const modalSpy = jest.spyOn(modalService, 'open')

    let modal: NgbModalRef

    modalService.activeInstances.subscribe((ngbmodalRef) => {
      modal = ngbmodalRef[0]
    })

    const canDeactivate = guard.canDeactivate(component)

    expect(canDeactivate).toHaveProperty('closed') // returns confirm dialog subject
    expect(modalSpy).toHaveBeenCalled()
    expect(modal).not.toBeNull()

    const saveSpy = jest.spyOn(component, 'saveViewConfig')
    modal.componentInstance.alternativeClicked.emit()
    expect(saveSpy).toHaveBeenCalled()
  })

  it('should not save if user proceeds on warn', () => {
    jest
      .spyOn(DocumentListComponent.prototype, 'savedViewIsModified', 'get')
      .mockImplementation(() => {
        return true
      })

    jest.spyOn(settingsService, 'get').mockImplementation(() => {
      return true
    })

    const modalSpy = jest.spyOn(modalService, 'open')

    let modal: NgbModalRef

    modalService.activeInstances.subscribe((ngbmodalRef) => {
      modal = ngbmodalRef[0]
    })

    const canDeactivate = guard.canDeactivate(component)

    expect(canDeactivate).toHaveProperty('closed') // returns confirm dialog subject
    expect(modalSpy).toHaveBeenCalled()
    expect(modal).not.toBeNull()

    const saveSpy = jest.spyOn(component, 'saveViewConfig')
    modal.componentInstance.confirmClicked.emit()
    expect(saveSpy).not.toHaveBeenCalled()
  })
})
