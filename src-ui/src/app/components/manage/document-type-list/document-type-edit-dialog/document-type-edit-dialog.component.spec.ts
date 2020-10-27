import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DocumentTypeEditDialogComponent } from './document-type-edit-dialog.component';

describe('DocumentTypeEditDialogComponent', () => {
  let component: DocumentTypeEditDialogComponent;
  let fixture: ComponentFixture<DocumentTypeEditDialogComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DocumentTypeEditDialogComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(DocumentTypeEditDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
