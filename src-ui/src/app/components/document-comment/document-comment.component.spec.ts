import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DocumentCommentComponent } from './document-comment.component';

describe('DocumentCommentComponent', () => {
  let component: DocumentCommentComponent;
  let fixture: ComponentFixture<DocumentCommentComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DocumentCommentComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(DocumentCommentComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});