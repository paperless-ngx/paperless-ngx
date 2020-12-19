import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DocumentCardLargeComponent } from './document-card-large.component';

describe('DocumentCardLargeComponent', () => {
  let component: DocumentCardLargeComponent;
  let fixture: ComponentFixture<DocumentCardLargeComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DocumentCardLargeComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(DocumentCardLargeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
