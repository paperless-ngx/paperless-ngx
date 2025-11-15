import { ComponentFixture, TestBed } from '@angular/core/testing'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DeletionRequestDetailComponent } from './deletion-request-detail.component'
import { DeletionRequestService } from 'src/app/services/rest/deletion-request.service'
import { ToastService } from 'src/app/services/toast.service'
import { DeletionRequestStatus } from 'src/app/data/deletion-request'

describe('DeletionRequestDetailComponent', () => {
  let component: DeletionRequestDetailComponent
  let fixture: ComponentFixture<DeletionRequestDetailComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DeletionRequestDetailComponent, HttpClientTestingModule],
      providers: [NgbActiveModal, DeletionRequestService, ToastService],
    }).compileComponents()

    fixture = TestBed.createComponent(DeletionRequestDetailComponent)
    component = fixture.componentInstance
    component.deletionRequest = {
      id: 1,
      created_at: '2024-01-01',
      updated_at: '2024-01-01',
      requested_by_ai: true,
      ai_reason: 'Test reason',
      user: 1,
      user_username: 'testuser',
      status: DeletionRequestStatus.Pending,
      documents: [1, 2],
      documents_detail: [],
      document_count: 2,
      impact_summary: {
        document_count: 2,
        documents: [],
        affected_tags: [],
        affected_correspondents: [],
        affected_types: [],
      },
    }
    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })
})
