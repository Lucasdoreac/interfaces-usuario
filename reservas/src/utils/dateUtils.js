/** Serializes the selected instant as UTC without shifting it a second time. */
const formatDateForMongoDB = (date) => {
  return date.toISOString();
};

export { formatDateForMongoDB };
