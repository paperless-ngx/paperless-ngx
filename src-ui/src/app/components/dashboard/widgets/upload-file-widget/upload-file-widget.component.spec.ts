import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { RouterTestingModule } from '@angular/router/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { routes } from 'src/app/app-routing.module'
import { PermissionsGuard } from 'src/app/guards/permissions.guard'
import { PermissionsService } from 'src/app/services/permissions.service'
import { UploadDocumentsService } from 'src/app/services/upload-documents.service'
import { UploadFileWidgetComponent } from './upload-file-widget.component'

describe('UploadFileWidgetComponent', () => {
  let fixture: ComponentFixture<UploadFileWidgetComponent>
  let uploadDocumentsService: UploadDocumentsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        RouterTestingModule.withRoutes(routes),
        NgxBootstrapIconsModule.pick(allIcons),
        UploadFileWidgetComponent,
      ],
      providers: [
        PermissionsGuard,
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
          },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    fixture = TestBed.createComponent(UploadFileWidgetComponent)

    fixture.detectChanges()
  })

  it('should support browse files', () => {
    const fileInput = fixture.debugElement.query(By.css('input'))
    const clickSpy = jest.spyOn(fileInput.nativeElement, 'click')
    fixture.debugElement
      .query(By.css('button'))
      .nativeElement.dispatchEvent(new Event('click'))
    expect(clickSpy).toHaveBeenCalled()
  })

  it('should upload files', () => {
    const uploadSpy = jest.spyOn(uploadDocumentsService, 'uploadFiles')
    fixture.debugElement
      .query(By.css('input'))
      .nativeElement.dispatchEvent(new Event('change'))
    expect(uploadSpy).toHaveBeenCalled()
  })
})
