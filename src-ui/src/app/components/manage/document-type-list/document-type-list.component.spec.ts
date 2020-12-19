import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DocumentTypeListComponent } from './document-type-list.component';

describe('DocumentTypeListComponent', () => {
  let component: DocumentTypeListComponent;
  let fixture: ComponentFixture<DocumentTypeListComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DocumentTypeListComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(DocumentTypeListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
