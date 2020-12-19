import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CorrespondentListComponent } from './correspondent-list.component';

describe('CorrespondentListComponent', () => {
  let component: CorrespondentListComponent;
  let fixture: ComponentFixture<CorrespondentListComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ CorrespondentListComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(CorrespondentListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
