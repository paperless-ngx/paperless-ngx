import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DocumentCardSmallComponent } from './document-card-small.component';

describe('DocumentCardSmallComponent', () => {
  let component: DocumentCardSmallComponent;
  let fixture: ComponentFixture<DocumentCardSmallComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DocumentCardSmallComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(DocumentCardSmallComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
