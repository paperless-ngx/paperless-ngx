import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CheckComponent } from './check.component';

describe('CheckComponent', () => {
  let component: CheckComponent;
  let fixture: ComponentFixture<CheckComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ CheckComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(CheckComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
