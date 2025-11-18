import { HttpClientTestingModule } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { DeletionRequestService } from 'src/app/services/rest/deletion-request.service'
import { ToastService } from 'src/app/services/toast.service'
import { DeletionRequestsComponent } from './deletion-requests.component'

describe('DeletionRequestsComponent', () => {
  let component: DeletionRequestsComponent
  let fixture: ComponentFixture<DeletionRequestsComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DeletionRequestsComponent, HttpClientTestingModule],
      providers: [DeletionRequestService, ToastService],
    }).compileComponents()

    fixture = TestBed.createComponent(DeletionRequestsComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })
})
