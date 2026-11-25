import React from "react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

const DatePickerComponent = ({ selectedDate, onDateChange, minDate }) => {
  return (
    <div className="datepicker-component">
      <DatePicker
        selected={selectedDate}
        onChange={onDateChange}
        minDate={minDate}
        dateFormat="dd/MM/yyyy"
        showMonthDropdown
        showYearDropdown
        dropdownMode="select"
      />
    </div>
  );
};

export default DatePickerComponent;
